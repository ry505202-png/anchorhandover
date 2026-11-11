from __future__ import annotations

import weakref
from datetime import datetime, timezone
from typing import Any

import streamlit as st
from streamlit.errors import StreamlitAPIException
from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx

from core.db import HandoverDatabase, open_seeded_database
from core.handover import STAGE_LABELS, demo_role_tag
from core.models import (
    WORKFLOW_ORDER,
    HandoverSession,
    LLMProviderName,
    Member,
    ReviewDecision,
    WorkflowStage,
)

PAGE_BY_STAGE = {
    WorkflowStage.CONNECT: "pages/1_Connect.py",
    WorkflowStage.RECONSTRUCT: "pages/2_Reconstruct.py",
    WorkflowStage.VERIFY: "pages/3_Verify.py",
    WorkflowStage.REVIEW: "pages/4_Review.py",
    WorkflowStage.HANDOVER: "pages/5_Handover.py",
}

# Tracks per-run ParallelFragmentCoordinator instances where the shared chrome
# (sidebar role/provider selectors, title, stepper) has already rendered.
# Guarantees chrome renders once per script run both under st.navigation() and
# when Streamlit's pages/-directory runner executes a page module directly.
_RENDERED_COORDINATORS: weakref.WeakSet[Any] = weakref.WeakSet()


def _configure_page_once() -> None:
    try:
        st.set_page_config(
            page_title="AnchorHandover — Evidence-First Project Handover",
            page_icon="🔐",
            layout="wide",
        )
    except StreamlitAPIException:
        pass


def _render_stepper(session: HandoverSession | None) -> None:
    current_idx = WORKFLOW_ORDER.index(session.stage) if session else 0
    cols = st.columns(len(WORKFLOW_ORDER))
    for idx, stage in enumerate(WORKFLOW_ORDER):
        label = STAGE_LABELS[stage]
        with cols[idx]:
            if session is None:
                if idx == 0:
                    st.info(f"**{label}** (Active)")
                else:
                    st.caption(label)
            elif idx < current_idx or (
                stage == WorkflowStage.HANDOVER and session.review_decision == ReviewDecision.APPROVED
            ):
                st.success(f"✓ {label}")
            elif idx == current_idx:
                st.info(f"**● {label}**")
            else:
                st.caption(f"○ {label}")


def _mark_chrome_rendered() -> None:
    ctx = get_script_run_ctx()
    if ctx is not None and ctx.parallel_coordinator is not None:
        _RENDERED_COORDINATORS.add(ctx.parallel_coordinator)


def _is_chrome_rendered() -> bool:
    ctx = get_script_run_ctx()
    return (
        ctx is not None
        and ctx.parallel_coordinator is not None
        and ctx.parallel_coordinator in _RENDERED_COORDINATORS
    )


def render_app_shell(
    db: HandoverDatabase | None = None,
    *,
    configure_page: bool = False,
) -> tuple[HandoverDatabase, dict[str, Member], Member]:
    """Render shared sidebar (Demo Role Selector, LLM Provider, SQLite sessions) and stage stepper."""
    if configure_page:
        _configure_page_once()

    db = db or open_seeded_database()
    members = db.list_members()
    members_by_id = {m.id: m for m in members}

    _mark_chrome_rendered()

    with st.sidebar:
        st.title("🔐 AnchorHandover")
        st.caption("Prevent Critical Knowledge From Leaving With People")

        actor_options = [m.id for m in members]
        preferred_actor = st.session_state.get("_persisted_demo_role_id", "priya")
        default_actor_idx = (
            actor_options.index(preferred_actor)
            if preferred_actor in actor_options
            else (actor_options.index("priya") if "priya" in actor_options else 0)
        )
        actor_id = st.selectbox(
            "Demo Role Selector (Lead / Departing member / Incoming member)",
            options=actor_options,
            index=default_actor_idx,
            key="demo_role_select",
            format_func=lambda mid: (
                f"{demo_role_tag(members_by_id[mid])} — {members_by_id[mid].name} "
                f"({members_by_id[mid].role}) [{members_by_id[mid].max_access_label.value}]"
            ),
        )
        st.session_state["_persisted_demo_role_id"] = actor_id
        actor = members_by_id[actor_id]

        st.markdown(
            f"- **Demo Role:** `{demo_role_tag(actor)}`\n"
            f"- **Clearance Label:** `{actor.max_access_label.value}`\n"
            f"- **Capabilities:** `{', '.join(actor.capabilities) or 'none'}`\n"
            f"- **Can Verify/Edit Claims:** `{actor.can_verify and not actor.is_external}`\n"
            f"- **Can Approve Final:** `{actor.can_approve and not actor.is_external}`"
        )

        st.divider()
        provider_options = [p.value for p in LLMProviderName]
        preferred_provider = st.session_state.get("_persisted_llm_provider", LLMProviderName.MOCK.value)
        default_prov_idx = (
            provider_options.index(preferred_provider) if preferred_provider in provider_options else 0
        )
        selected_provider = st.selectbox(
            "LLM Provider",
            options=provider_options,
            index=default_prov_idx,
            key="llm_provider_select",
            format_func=lambda p: {
                "mock": "MOCK (Deterministic Cached JSON)",
                "gemini": "Gemini (Free Tier REST)",
                "groq": "Groq (Free Tier REST)",
            }.get(p, p),
            help="MOCK returns cached JSON with zero API quota needed. Gemini & Groq use free-tier APIs.",
        )
        st.session_state["_persisted_llm_provider"] = selected_provider
        if selected_provider != LLMProviderName.MOCK.value:
            st.text_input(
                f"{selected_provider.title()} API Key (or set {selected_provider.upper()}_API_KEY)",
                type="password",
                key="llm_api_key_input",
            )

        st.divider()
        sessions = db.list_sessions()
        if st.button("+ New Handover Session", width="stretch"):
            st.session_state["active_session_id"] = None
            st.session_state.pop("_synced_active_sid", None)
            st.session_state.pop("saved_sessions_select", None)
            st.switch_page(PAGE_BY_STAGE[WorkflowStage.CONNECT])

        if sessions:
            session_ids = [s.id for s in sessions]
            current_sid = st.session_state.get("active_session_id")
            if current_sid not in session_ids and current_sid is not None:
                current_sid = session_ids[0]
            if current_sid is None and "active_session_id" not in st.session_state:
                current_sid = session_ids[0]
                st.session_state["active_session_id"] = current_sid

            if current_sid in session_ids:
                if st.session_state.get("_synced_active_sid") != current_sid:
                    st.session_state["saved_sessions_select"] = current_sid
                    st.session_state["_synced_active_sid"] = current_sid
                chosen_sid = st.selectbox(
                    "Saved Sessions (SQLite)",
                    options=session_ids,
                    index=session_ids.index(current_sid),
                    key="saved_sessions_select",
                    format_func=lambda sid: next(
                        f"{s.id} ({s.project_id} -> {s.recipient_member_id}, {s.stage.value})"
                        for s in sessions
                        if s.id == sid
                    ),
                )
                if chosen_sid != st.session_state.get("active_session_id"):
                    st.session_state["active_session_id"] = chosen_sid
                    st.session_state["_synced_active_sid"] = chosen_sid
                    chosen_obj = db.get_session(chosen_sid)
                    target = (
                        PAGE_BY_STAGE[chosen_obj.stage]
                        if chosen_obj
                        else PAGE_BY_STAGE[WorkflowStage.CONNECT]
                    )
                    st.switch_page(target)

        st.divider()
        if st.button("Reset Synthetic Demo Workspace", width="stretch"):
            db.init_and_seed(reset=True)
            reset_actor = db.get_member(actor.id) or actor
            db.append_audit_log(
                session_id="system",
                actor=reset_actor,
                action="workspace_reset",
                target_id="demo_workspace",
                details={"synthetic_only": True},
                created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            st.session_state.pop("active_session_id", None)
            st.session_state.pop("_synced_active_sid", None)
            st.session_state.pop("saved_sessions_select", None)
            st.switch_page(PAGE_BY_STAGE[WorkflowStage.CONNECT])

    active_sid = st.session_state.get("active_session_id")
    active_session = db.get_session(active_sid) if active_sid else None

    st.title("Prevent Critical Knowledge From Leaving With People")
    st.caption(
        "Evidence-first, permission-aware handover system · Workflow: "
        "**Connect → Reconstruct → Verify → Review → Handover**"
    )
    _render_stepper(active_session)
    st.divider()

    return db, members_by_id, actor


def ensure_app_shell() -> tuple[HandoverDatabase, dict[str, Member], Member]:
    """Ensure the shared sidebar, title, and workflow stepper render once per page run."""
    if not _is_chrome_rendered():
        return render_app_shell(configure_page=True)
    db = open_seeded_database()
    members_by_id = {m.id: m for m in db.list_members()}
    actor_id = st.session_state.get(
        "demo_role_select",
        st.session_state.get("_persisted_demo_role_id", "priya"),
    )
    actor = members_by_id.get(actor_id) or next(iter(members_by_id.values()))
    return db, members_by_id, actor


def main() -> None:
    import app as app_shell

    app_shell._configure_page_once()

    connect_page = st.Page("pages/1_Connect.py", title="1. Connect", icon="🔌", default=True)
    reconstruct_page = st.Page("pages/2_Reconstruct.py", title="2. Reconstruct", icon="🧠")
    verify_page = st.Page("pages/3_Verify.py", title="3. Verify", icon="✅")
    review_page = st.Page("pages/4_Review.py", title="4. Review", icon="📋")
    handover_page = st.Page("pages/5_Handover.py", title="5. Handover", icon="📦")
    pg = st.navigation([connect_page, reconstruct_page, verify_page, review_page, handover_page])

    app_shell.render_app_shell(configure_page=False)
    pg.run()


if __name__ == "__main__":
    main()
