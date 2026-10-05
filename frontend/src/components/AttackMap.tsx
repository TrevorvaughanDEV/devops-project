import { useMemo, useState } from "react";
import { geoGraticule10, geoInterpolate, geoNaturalEarth1, geoPath } from "d3-geo";
import { feature, mesh } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import world from "world-atlas/countries-110m.json";
import type { Attempt, MapPoint, Meta } from "../api";
import { ago, flag, num, place } from "../format";

const W = 960;
const H = 470;

const topo = world as unknown as Topology<{ countries: GeometryCollection; land: GeometryCollection }>;
// Antarctica only takes up space here; nobody attacks from there.
const countries = feature(topo, topo.objects.countries);
countries.features = countries.features.filter((f) => f.id !== "010");
const borders = mesh(topo, topo.objects.countries, (a, b) => a !== b);

const projection = geoNaturalEarth1().fitExtent(
  [[4, 4], [W - 4, H + 70]],
  { type: "Sphere" },
);
const path = geoPath(projection);
const spherePath = path({ type: "Sphere" }) ?? "";
const graticulePath = path(geoGraticule10()) ?? "";
const landPath = path(countries) ?? "";
const borderPath = path(borders) ?? "";

export type Arc = { key: number; from: [number, number]; ip: string };

function arcPath(from: [number, number], to: [number, number]) {
  const interp = geoInterpolate(from, to);
  const pts = Array.from({ length: 33 }, (_, i) => projection(interp(i / 32)));
  if (pts.some((p) => !p)) return "";
  // Lift the middle of the great circle so arcs read as flight paths, not borders.
  const lift = Math.min(90, Math.hypot(pts[0]![0] - pts[32]![0], pts[0]![1] - pts[32]![1]) * 0.18);
  return pts
    .map((p, i) => {
      const y = p![1] - Math.sin((Math.PI * i) / 32) * lift;
      return `${i ? "L" : "M"}${p![0].toFixed(1)},${y.toFixed(1)}`;
    })
    .join("");
}

type Props = {
  meta: Meta | null;
  points: MapPoint[];
  arcs: Arc[];
  mine: Set<number>;
  onSelect: (ip: string) => void;
};

export function AttackMap({ meta, points, arcs, mine, onSelect }: Props) {
  const [hover, setHover] = useState<MapPoint | null>(null);
  const home = meta ? ([meta.server.lon, meta.server.lat] as [number, number]) : null;
  const homeXY = home ? projection(home) : null;
  const max = Math.max(1, ...points.map((p) => p.count));

  const placed = useMemo(
    () =>
      points
        .map((p) => ({ p, xy: projection([p.lon, p.lat]) }))
        .filter((d): d is { p: MapPoint; xy: [number, number] } => !!d.xy)
        // Small dots on top so busy attackers don't hide quiet ones.
        .sort((a, b) => b.p.count - a.p.count),
    [points],
  );

  return (
    <figure className="map" aria-label={`World map of ${points.length} attacking addresses in the last 24 hours`}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-hidden="false">
        <path d={spherePath} className="map-sea" />
        <path d={graticulePath} className="map-grid" />
        <path d={landPath} className="map-land" />
        <path d={borderPath} className="map-border" />

        {placed.map(({ p, xy }, i) => {
          const r = 2.5 + 9 * Math.sqrt(p.count / max);
          return (
            <circle
              key={p.ip}
              cx={xy[0]}
              cy={xy[1]}
              r={r}
              className="map-point"
              tabIndex={i < 15 ? 0 : -1}
              aria-label={`${p.ip}, ${place(p.city, p.country)}, ${p.count} attempts`}
              onMouseEnter={() => setHover(p)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(p)}
              onBlur={() => setHover(null)}
              onClick={() => onSelect(p.ip)}
              onKeyDown={(e) => e.key === "Enter" && onSelect(p.ip)}
            />
          );
        })}

        {home &&
          arcs.map((a) => {
            const d = arcPath(a.from, home);
            const start = projection(a.from);
            return (
              d && (
                <g key={a.key} className={mine.has(a.key) ? "map-arc map-arc-mine" : "map-arc"}>
                  <path d={d} pathLength={1} />
                  {start && <circle cx={start[0]} cy={start[1]} r={4} />}
                  {start && mine.has(a.key) && (
                    <text x={start[0]} y={start[1] - 10} textAnchor="middle">You</text>
                  )}
                </g>
              )
            );
          })}

        {homeXY && (
          <g className="map-home" transform={`translate(${homeXY[0]},${homeXY[1]})`}>
            <circle r={13} className="map-home-ring" />
            <circle r={4.5} />
          </g>
        )}
      </svg>

      {hover && (() => {
        const xy = projection([hover.lon, hover.lat]);
        if (!xy) return null;
        const left = (xy[0] / W) * 100;
        return (
          <div
            className="map-tip"
            style={{ left: `${left}%`, top: `${(xy[1] / H) * 100}%` }}
            data-side={left > 70 ? "left" : "right"}
          >
            <strong>{flag(hover.country)} {hover.ip}</strong>
            <span>{place(hover.city, hover.country)}</span>
            <span>{num(hover.count)} attempts, last {ago(hover.last)}</span>
          </div>
        );
      })()}

      {homeXY && meta && (
        <figcaption
          className="map-home-label"
          style={{ left: `${(homeXY[0] / W) * 100}%`, top: `${(homeXY[1] / H) * 100}%` }}
        >
          My server, {meta.server.label}
        </figcaption>
      )}
    </figure>
  );
}

/** Turn a live attempt into an arc, if it has a location. */
export function toArc(a: Attempt): Arc | null {
  return a.lat == null || a.lon == null ? null : { key: a.id, from: [a.lon, a.lat], ip: a.ip };
}
