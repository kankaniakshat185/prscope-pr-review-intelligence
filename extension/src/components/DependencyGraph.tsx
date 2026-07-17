"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

// Dynamically import ForceGraph2D with SSR disabled
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

export default function DependencyGraph({ graphData }: { graphData: any }) {
  const [data, setData] = useState({ nodes: [], links: [] });

  useEffect(() => {
    if (!graphData || !graphData.modified_functions) return;

    const nodesMap = new Map();
    const links = [];

    // Add nodes and edges
    graphData.modified_functions.forEach((func: any) => {
      if (!nodesMap.has(func.function)) {
        nodesMap.set(func.function, { id: func.function, name: func.function, val: 1.5, color: "#da3633" });
      }

      func.called_by?.forEach((caller: string) => {
        if (!nodesMap.has(caller)) {
          nodesMap.set(caller, { id: caller, name: caller, val: 1, color: "#8b949e" });
        }
        links.push({ source: caller, target: func.function });
      });

      func.calls?.forEach((callee: string) => {
        if (!nodesMap.has(callee)) {
          nodesMap.set(callee, { id: callee, name: callee, val: 1, color: "#8b949e" });
        }
        links.push({ source: func.function, target: callee });
      });
    });

    setData({
      nodes: Array.from(nodesMap.values()),
      links: links,
    });
  }, [graphData]);

  if (data.nodes.length === 0) {
    return <div className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] text-center py-4">No dependency edges to visualize.</div>;
  }

  return (
    <div className="border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md overflow-hidden bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] h-[300px]">
      <ForceGraph2D
        graphData={data}
        nodeLabel="name"
        nodeColor={(node: any) => node.color}
        nodeRelSize={4}
        width={340} 
        height={300}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        linkColor={() => "rgba(139, 148, 158, 0.5)"}
        d3VelocityDecay={0.3}
      />
    </div>
  );
}
