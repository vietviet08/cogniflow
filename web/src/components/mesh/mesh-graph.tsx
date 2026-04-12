"use client";

import dynamic from "next/dynamic";
import type { ConflictMeshPayload } from "@/lib/api/types";

const MeshGraph3DClient = dynamic(
    () => import("./mesh-graph-3d-client"),
    { ssr: false, loading: () => <div className="flex w-full h-[500px] items-center justify-center animate-pulse text-muted-foreground">Initializing 3D Space...</div> }
);

export default function MeshGraph({ payload }: { payload: ConflictMeshPayload }) {
    return <MeshGraph3DClient payload={payload} />;
}
