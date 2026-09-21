export interface SwarmObject { id: string; object_type: string; title: string; status: string; version: number; created_at: string; updated_at: string; tags: string[]; metadata: Record<string, unknown> }
export interface ObjectRef { objectId: string; objectType: string; version?: number }
export interface SwarmEvent { sequence: number; event_id: string; event_type: string; object_id: string | null; timestamp: string; trace_id: string; causation_id: string | null; payload: { snapshot?: SwarmObject } }
export interface SwarmEdge { id: string; from_object_id: string; to_object_id: string; edge_type: string }
export interface Graph { nodes: SwarmObject[]; edges: SwarmEdge[]; truncated: boolean; recommended_view: string }
