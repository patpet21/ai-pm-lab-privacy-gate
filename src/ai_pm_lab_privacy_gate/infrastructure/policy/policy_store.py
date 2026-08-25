from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ai_pm_lab_privacy_gate.domain.company_policy import CompanyPolicy
from ai_pm_lab_privacy_gate.domain.plans import PlanCode, normalize_plan
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import (
    SecretStore,
    platform_secret_store,
)


STATE_SECRET = "business.team_state.v1"
MANAGED_MARKER_SECRET = "business.managed.v1"


class PolicyCacheError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TeamState:
    plan: PlanCode = PlanCode.BASIC
    organization_id: str = ""
    organization_name: str = ""
    role: str = ""
    membership_status: str = "individual"
    seat_limit: int | None = None
    device_limit_per_member: int | None = None
    policy: CompanyPolicy | None = None
    synced_at: str = ""
    entitlement_status: str = "active"

    @property
    def managed(self) -> bool:
        return (
            self.plan in {PlanCode.BUSINESS, PlanCode.ENTERPRISE}
            and bool(self.organization_id)
            and self.membership_status == "active"
            and self.policy is not None
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "plan": self.plan.value,
            "organization_id": self.organization_id,
            "organization_name": self.organization_name,
            "role": self.role,
            "membership_status": self.membership_status,
            "seat_limit": self.seat_limit,
            "device_limit_per_member": self.device_limit_per_member,
            "policy": self.policy.to_dict() if self.policy else None,
            "synced_at": self.synced_at,
            "entitlement_status": self.entitlement_status,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "TeamState":
        raw_policy = payload.get("policy")
        policy = (
            CompanyPolicy.from_dict(raw_policy)
            if isinstance(raw_policy, Mapping)
            else None
        )
        seat_limit_raw = payload.get("seat_limit")
        device_limit_raw = payload.get("device_limit_per_member")
        return cls(
            plan=normalize_plan(str(payload.get("plan") or PlanCode.BASIC.value)),
            organization_id=str(payload.get("organization_id") or ""),
            organization_name=str(payload.get("organization_name") or ""),
            role=str(payload.get("role") or ""),
            membership_status=str(payload.get("membership_status") or "individual"),
            seat_limit=int(seat_limit_raw) if seat_limit_raw is not None else None,
            device_limit_per_member=(
                int(device_limit_raw) if device_limit_raw is not None else None
            ),
            policy=policy,
            synced_at=str(payload.get("synced_at") or ""),
            entitlement_status=str(payload.get("entitlement_status") or "active"),
        )


class SecureTeamStateStore:
    """Keep the last valid company policy in the operating-system protected vault."""

    def __init__(
        self,
        data_dir: str | Path,
        secret_store: SecretStore | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.secrets = secret_store or platform_secret_store(self.data_dir)

    def load(self) -> TeamState:
        try:
            raw = self.secrets.get(STATE_SECRET)
            managed_marker = self.secrets.get(MANAGED_MARKER_SECRET)
        except Exception as error:
            raise PolicyCacheError(
                "PrivacyGate cannot read the protected company-policy cache."
            ) from error

        if not raw:
            if managed_marker:
                raise PolicyCacheError(
                    "This device is company-managed but its cached policy is unavailable. "
                    "Reconnect and refresh the company policy before using AI or managed apps."
                )
            return TeamState()

        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("state must be a JSON object")
            state = TeamState.from_dict(payload)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise PolicyCacheError(
                "The protected company-policy cache is invalid. "
                "PrivacyGate will not silently downgrade this managed device."
            ) from error

        if managed_marker and not state.managed:
            raise PolicyCacheError(
                "The cached company state is incomplete for a managed device. "
                "Refresh the policy before using AI or managed apps."
            )
        return state

    def save(self, state: TeamState) -> None:
        payload = json.dumps(
            state.to_dict(),
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            self.secrets.set(STATE_SECRET, payload)
            if state.managed:
                self.secrets.set(MANAGED_MARKER_SECRET, "1")
            else:
                self.secrets.delete(MANAGED_MARKER_SECRET)
        except Exception as error:
            raise PolicyCacheError(
                "PrivacyGate could not securely cache the company policy."
            ) from error

    def clear(self) -> None:
        try:
            self.secrets.delete(STATE_SECRET)
            self.secrets.delete(MANAGED_MARKER_SECRET)
        except Exception as error:
            raise PolicyCacheError(
                "PrivacyGate could not clear the local company-policy cache."
            ) from error
