from __future__ import annotations

from job_agent.profile import SearchProfile


def hh_search_queries(profile: SearchProfile) -> list[str]:
    if profile.hh_search_queries:
        return [q.strip() for q in profile.hh_search_queries if q and q.strip()]
    if profile.hh_search_text:
        return [profile.hh_search_text.strip()]
    if profile.desired_roles:
        return [" OR ".join(profile.desired_roles[:4])]
    return ["руководитель проект ритейл"]
