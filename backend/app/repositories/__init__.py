"""MongoDB-backed repository layer. Routes -> Services -> Repositories ->
MongoDB -- no raw MongoDB queries belong in a route handler.

Each repository here is a pure data-access class: it knows how to read/write
its own collection and nothing about HTTP, inference, or SMS. Orchestration
that spans repositories (e.g. "create an incident after a job completes")
lives in the service layer (app/services/*.py), not inside a repository.
"""

from __future__ import annotations
