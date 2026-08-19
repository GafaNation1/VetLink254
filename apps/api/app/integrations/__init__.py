# apps/api/app/integrations/__init__.py — External-provider integrations, isolated behind clean interfaces (architecture.md Section 7)
# Each client here wraps ONE external system behind a small interface so the real provider can be
# swapped in later without touching app code. Today it holds only the KVB verification bridge.
