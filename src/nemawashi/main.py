"""Nemawashi Enterprise Multi-Agent Governance Engine - FastAPI Ingress Gateway & CLI Demo.

Provides:
1. Non-blocking FastAPI Ingress Gateway with /resume POST endpoint for asynchronous HITL resumption.
2. Rich interactive console demonstration of sequential consensus, structured memory contracts,
   mitigation loop watchdog, and cryptographically chained audit logging.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional
import uuid

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from nemawashi.core.engine import NemawashiEngine
from nemawashi.core.models import AgentProposal
from nemawashi.audit.ledger import verify_ledger_chain

console = Console()

# -----------------------------------------------------------------------------
# FastAPI Ingress Gateway Application
# -----------------------------------------------------------------------------

app = FastAPI(
    title="Nemawashi Multi-Agent Governance Engine Gateway",
    description="Non-blocking ingress gateway for asynchronous human-in-the-loop deliberation callbacks.",
    version="1.1.0",
)


class ResumeProposalRequest(BaseModel):
    """Payload submitted to /resume to complete suspended HITL escalation."""

    proposal_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]{1,128}$",
        description="Proposal identifier matching suspended state",
    )
    approved: bool = Field(
        ..., description="Operator decision: True to authorize, False to veto"
    )
    rationale: str = Field(
        default="Operator decision supplied via FastAPI gateway callback",
        description="Written justification for operator decision",
    )
    auth_token: Optional[str] = Field(
        default=None,
        description="Cryptographic HMAC or callback authorization token",
    )


class ResumeProposalResponse(BaseModel):
    """Response returned upon successful resumption and ledger commitment."""

    status: str
    proposal_id: str
    execution_permitted: bool
    human_approved: Optional[bool]
    verdict: str
    composite_risk_score: int
    audit_record_hash: Optional[str]
    audit_committed: bool
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    timestamp: str


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    """Liveness probe for the governance engine gateway."""
    return {"status": "healthy", "service": "nemawashi-governance-engine"}


def compute_resume_signature(
    proposal_id: str,
    approved: bool,
    rationale: str,
    secret: str,
) -> str:
    """Compute deterministic HMAC-SHA256 signature for resume callback payload."""
    payload = f"{proposal_id}:{str(approved).lower()}:{rationale}"
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@app.post(
    "/resume",
    response_model=ResumeProposalResponse,
    status_code=status.HTTP_200_OK,
    tags=["Governance"],
)
def resume_deliberation(
    request: ResumeProposalRequest,
    x_nemawashi_signature: Optional[str] = Header(default=None, alias="X-Nemawashi-Signature"),
) -> ResumeProposalResponse:
    """External callback endpoint for resuming suspended human-in-the-loop deliberations.

    Enforces mandatory HMAC-SHA256 signature verification using NEMAWASHI_WEBHOOK_SECRET.
    Loads the serialized state from local storage, applies operator decision and rationale,
    resumes graph execution, and seals the final record in the immutable audit ledger.
    """
    secret = os.getenv("NEMAWASHI_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="NEMAWASHI_WEBHOOK_SECRET not configured",
        )

    # 1. Extract signature from header or body
    sig_from_header = (
        x_nemawashi_signature
        if isinstance(x_nemawashi_signature, str)
        else None
    )
    raw_sig = sig_from_header or request.auth_token
    if not raw_sig or not isinstance(raw_sig, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing HMAC-SHA256 callback signature (provide X-Nemawashi-Signature header or auth_token in payload)",
        )

    provided_sig = raw_sig.strip()
    if provided_sig.lower().startswith("sha256="):
        provided_sig = provided_sig[7:].strip()

    # 2. Compute expected HMAC-SHA256 digest
    expected_sig = compute_resume_signature(
        proposal_id=request.proposal_id,
        approved=request.approved,
        rationale=request.rationale,
        secret=secret,
    )

    # 3. Constant-time comparison
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC-SHA256 callback signature",
        )

    # 4. Resume execution through Nemawashi engine
    engine = NemawashiEngine()
    try:
        final_state = engine.resume_proposal(
            proposal_id=request.proposal_id,
            approved=request.approved,
            rationale=request.rationale,
        )
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suspended proposal '{request.proposal_id}' not found in local storage.",
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid proposal data: {str(err)}",
        ) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume proposal '{request.proposal_id}': {str(err)}",
        ) from err

    res = final_state.get("resolution")
    verdict = res.verdict if res else "UNKNOWN"
    risk_score = res.composite_risk_score if res else 100

    return ResumeProposalResponse(
        status="RESUMED",
        proposal_id=request.proposal_id,
        execution_permitted=final_state.get("execution_permitted", False),
        human_approved=final_state.get("human_approved"),
        verdict=verdict,
        composite_risk_score=risk_score,
        audit_record_hash=final_state.get("audit_record_hash"),
        audit_committed=final_state.get("audit_committed", False),
        prompt_tokens=final_state.get("prompt_tokens", 0),
        completion_tokens=final_state.get("completion_tokens", 0),
        total_cost_usd=final_state.get("total_cost_usd", 0.0),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# -----------------------------------------------------------------------------
# Rich Interactive Console Demonstration
# -----------------------------------------------------------------------------


def display_scenario_banner(scenario_num: int, title: str, description: str):
    console.print()
    console.print(
        Panel(
            f"[bold yellow]SCENARIO {scenario_num}: {title}[/bold yellow]\n[dim]{description}[/dim]",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )


def display_results_table(state: dict):
    table = Table(title="Stakeholder Structured Deliberation Record", box=box.ROUNDED)
    table.add_column("Stakeholder", style="bold cyan")
    table.add_column("Vote", style="bold")
    table.add_column("Risk Tags", style="magenta")
    table.add_column("Mitigation Requirements", style="green")

    votes = state.get("stakeholder_votes", {})
    for sid in ["security", "compliance", "finops", "sre"]:
        vote = votes.get(sid)
        if vote:
            vote_val = vote.vote
            color = (
                "green"
                if vote_val == "APPROVE"
                else "yellow"
                if vote_val == "MITIGATE"
                else "red"
            )
            tags = ", ".join(vote.risk_tags) if vote.risk_tags else "None"
            mitigations = (
                "\n".join(f"• {m}" for m in vote.mitigation_requirements)
                if vote.mitigation_requirements
                else "None"
            )
            table.add_row(
                sid.upper(), f"[{color}]{vote_val}[/{color}]", tags, mitigations
            )
        else:
            table.add_row(sid.upper(), "[dim]SKIPPED[/dim]", "N/A", "N/A")

    console.print(table)

    res = state.get("resolution")
    verdict = (
        res.verdict
        if res
        else ("CONSENSUS_VETO" if not state.get("policy_passed") else "UNKNOWN")
    )
    verdict_color = (
        "green"
        if verdict in ("UNANIMOUS_CONSENSUS", "CONDITIONAL_ALIGNMENT")
        else "red"
    )

    console.print(
        Panel(
            f"[bold]Final Verdict:[/bold] [{verdict_color}]{verdict}[/{verdict_color}]\n"
            f"[bold]Execution Permitted:[/bold] {'[green]YES[/green]' if state.get('execution_permitted') else '[red]NO[/red]'}\n"
            f"[bold]Composite Risk Score:[/bold] {res.composite_risk_score if res else 100}/100\n"
            f"[bold]Deliberation Round:[/bold] {state.get('current_round', 1)} / {state.get('max_rounds', 3)}\n"
            f"[bold]Loop Watchdog Intervened:[/bold] {state.get('loop_veto_triggered', False)}\n"
            f"[bold]Prompt Tokens:[/bold] {state.get('prompt_tokens', 0)} | [bold]Completion Tokens:[/bold] {state.get('completion_tokens', 0)}\n"
            f"[bold]Total Cost USD:[/bold] ${state.get('total_cost_usd', 0.0):.4f}\n"
            f"[bold]Suspended for HITL:[/bold] {state.get('suspended_for_hitl', False)}\n"
            f"[bold]Audit Record Hash:[/bold] [dim]{state.get('audit_record_hash')}[/dim]",
            title="Consensus Synthesis & Audit Seal",
            border_style=verdict_color,
        )
    )


def run_demo():
    console.print(
        Panel.fit(
            "[bold white on blue] NEMAWASHI ENTERPRISE MULTI-AGENT GOVERNANCE ENGINE [/bold white on blue]\n"
            "[dim]Autonomous Consensus Circle • Non-Blocking Async HITL • Watchdog • Chained Audit[/dim]",
            box=box.DOUBLE,
        )
    )

    engine = NemawashiEngine(max_rounds=3)

    # Scenario 1: Low-risk routine cache deployment (Unanimous Consensus)
    display_scenario_banner(
        1,
        "Routine Read-Replica Redis Cache Deployment",
        "Low-cost, zero PII, minimal blast radius deployment of caching layer.",
    )
    p1 = AgentProposal(
        proposal_id=str(uuid.uuid4())[:8],
        proposing_agent="agent-infra-provisioner",
        action_type="cache_cluster_scale",
        action_description="Scale Redis read-replicas from 2 to 4 to dampen peak traffic latency.",
        target_resource="cache-redis-read-pool",
        estimated_cost_usd=45.0,
        estimated_blast_radius=15,
        parameters={"nodes": 4, "cluster_type": "redis-6.x"},
    )
    state1 = engine.evaluate_proposal(p1)
    display_results_table(state1)

    # Scenario 2: Moderate-risk staging database migration (Conditional Alignment)
    display_scenario_banner(
        2,
        "Staging Database Schema Migration",
        "Moderate blast radius schema change requiring SRE rollbacks and FinOps tagging.",
    )
    p2 = AgentProposal(
        proposal_id=str(uuid.uuid4())[:8],
        proposing_agent="agent-db-migrator",
        action_type="schema_migration_ddl",
        action_description="Execute schema DDL migration to add index on user_sessions table.",
        target_resource="staging-aurora-postgres",
        estimated_cost_usd=120.0,
        estimated_blast_radius=60,
        parameters={
            "table": "user_sessions",
            "ddl": "CREATE INDEX CONCURRENTLY idx_user_sess",
        },
    )
    state2 = engine.evaluate_proposal(p2)
    display_results_table(state2)

    # Scenario 3: Hard Policy Violation (Immediate Structural VETO)
    display_scenario_banner(
        3,
        "Prohibited Destructive Operation",
        "Attempted destructive action on production database triggering deterministic pre-check VETO.",
    )
    p3 = AgentProposal(
        proposal_id=str(uuid.uuid4())[:8],
        proposing_agent="agent-rogue-cleaner",
        action_type="drop_production_database",
        action_description="Emergency clean-up dropping orphaned tables in production database.",
        target_resource="prod-primary-db",
        estimated_cost_usd=0.0,
        estimated_blast_radius=95,
        parameters={"force": True},
    )
    state3 = engine.evaluate_proposal(p3)
    display_results_table(state3)

    # Scenario 4: High-Value Infrastructure Expansion (Non-Blocking Asynchronous HITL Escalation)
    display_scenario_banner(
        4,
        "High-Value Multi-Region Compute Expansion (Non-Blocking HITL Escalation)",
        "Exceeds $500 threshold; thread suspends cleanly to disk and resumes via /resume callback.",
    )
    p4 = AgentProposal(
        proposal_id=str(uuid.uuid4())[:8],
        proposing_agent="agent-capacity-autoscaler",
        action_type="compute_cluster_expansion",
        action_description="Provision GPU inference cluster with 8x H100 nodes for batch processing.",
        target_resource="prod-gpu-cluster-us-east",
        estimated_cost_usd=2400.0,
        estimated_blast_radius=85,
        parameters={"gpu_count": 8, "sku": "h100-80gb"},
    )
    # Stage 1: Autonomous evaluation triggers HITL escalation and suspends cleanly
    state4_suspended = engine.evaluate_proposal(p4)
    display_results_table(state4_suspended)
    assert state4_suspended.get("suspended_for_hitl") is True

    # Stage 2: Simulating out-of-band operator callback via resume_proposal
    console.print(
        "[bold yellow]Simulating external callback from platform operator to /resume...[/bold yellow]"
    )
    state4_resumed = engine.resume_proposal(
        proposal_id=p4.proposal_id,
        approved=True,
        rationale="Executive VP approved after validating compute reservation budget",
    )
    display_results_table(state4_resumed)

    # Ledger Verification
    console.print()
    console.print(
        "[bold cyan]Executing SHA-256 Cryptographic Audit Ledger Verification...[/bold cyan]"
    )
    valid, message = engine.verify_audit_ledger()
    if valid:
        console.print(
            f"[bold green]✔ LEDGER INTEGRITY VERIFIED:[/bold green] {message}"
        )
    else:
        console.print(f"[bold red]✘ LEDGER COMPROMISED:[/bold red] {message}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        import uvicorn

        uvicorn.run("nemawashi.main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        run_demo()
