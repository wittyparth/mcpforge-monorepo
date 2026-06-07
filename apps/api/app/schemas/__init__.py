"""Pydantic schemas for MCPForge. Schemas are the only thing that
crosses layer boundaries: services return Pydantic models, routes
serialize Pydantic models, and ORM models never leave the service
layer. This is the cross-layer contract locked by the Wave 0 Skeleton.
"""
