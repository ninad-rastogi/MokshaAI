"""Model preference and routing services."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from llm.models import ModelProfile, UserModelPreference
from users.models import User


@dataclass(frozen=True)
class ModelSelection:
    """Selected primary profile plus at most one fallback for a generation run."""

    primary: ModelProfile
    fallback: ModelProfile | None = None

    @property
    def attempts(self) -> tuple[ModelProfile, ...]:
        return (self.primary, self.fallback) if self.fallback else (self.primary,)


def _eligible_profiles(ids: Iterable[str]) -> list[ModelProfile]:
    parsed_ids = []
    for raw_id in ids:
        try:
            parsed_ids.append(UUID(str(raw_id)))
        except TypeError, ValueError:
            continue
    if not parsed_ids:
        return []
    profiles = {
        profile.pk: profile
        for profile in ModelProfile.objects.filter(
            pk__in=parsed_ids,
            is_enabled=True,
        ).select_related("connection")
    }
    return [profiles[item] for item in parsed_ids if item in profiles]


def resolve_model_selection(
    *,
    user: User,
    chat_override_profile_id: str = "",
) -> ModelSelection:
    """Apply precedence: chat override, user primary, fallback, admin default."""

    ordered_ids: list[str] = []
    if chat_override_profile_id:
        ordered_ids.append(chat_override_profile_id)

    preference = getattr(user, "model_preference", None)
    if isinstance(preference, UserModelPreference):
        if preference.primary_profile_id:
            ordered_ids.append(str(preference.primary_profile_id))
        ordered_ids.extend(
            str(item) for item in preference.ordered_fallback_profile_ids
        )

    admin_default = (
        ModelProfile.objects.filter(is_enabled=True, is_admin_default=True)
        .select_related("connection")
        .first()
    )
    if admin_default:
        ordered_ids.append(str(admin_default.pk))

    seen: set[str] = set()
    deduped = []
    for profile_id in ordered_ids:
        if profile_id not in seen:
            seen.add(profile_id)
            deduped.append(profile_id)
    profiles = _eligible_profiles(deduped)
    if not profiles:
        raise ModelProfile.DoesNotExist("no_eligible_model_profile")
    return ModelSelection(
        primary=profiles[0],
        fallback=profiles[1] if len(profiles) > 1 else None,
    )
