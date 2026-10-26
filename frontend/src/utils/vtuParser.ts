/**
 * Scientific Visualization & VTK/VTU Post-Processing Utilities:
 * - Multi-colormap lookup tables (Viridis, Inferno, CoolWarm, Plasma, Jet)
 * - VTK XML UnstructuredGrid (.vtu) parser compatible with vtk.js & ParaView exports
 * - Exact Marching-Tetrahedra 3D Cross-Section Plane Slicer for tetrahedral volume meshes
 */

export type ScientificColormap = 'viridis' | 'inferno' | 'coolwarm' | 'plasma' | 'jet';

export type ClipPlaneAxis = 'none' | 'x' | 'y' | 'z';

export interface ClippingPlaneConfig {
  axis: ClipPlaneAxis;
  /** Normalized slice position in [-0.5, 0.5] across the domain span */
  offsetNormalized: number;
  invert: boolean;
}

const COLORMAP_STOPS: Record<ScientificColormap, Array<[number, number, number]>> = {
  viridis: [
    [0.267, 0.005, 0.329],
    [0.23, 0.322, 0.546],
    [0.128, 0.567, 0.551],
    [0.369, 0.788, 0.383],
    [0.993, 0.906, 0.144],
  ],
  inferno: [
    [0.001, 0.0, 0.014],
    [0.341, 0.062, 0.429],
    [0.735, 0.216, 0.33],
    [0.978, 0.557, 0.035],
    [0.988, 0.998, 0.645],
  ],
  coolwarm: [
    [0.23, 0.299, 0.754],
    [0.554, 0.69, 0.996],
    [0.865, 0.865, 0.865],
    [0.958, 0.603, 0.486],
    [0.706, 0.016, 0.15],
  ],
  plasma: [
    [0.05, 0.03, 0.528],
    [0.494, 0.012, 0.658],
    [0.798, 0.28, 0.47],
    [0.973, 0.58, 0.254],
    [0.94, 0.975, 0.131],
  ],
  jet: [
    [0.05, 0.2, 0.95],
    [0.0, 0.95, 0.95],
    [0.1, 0.95, 0.2],
    [0.98, 0.85, 0.0],
    [0.98, 0.12, 0.08],
  ],
};

/**
 * Interpolate a normalized scalar value t in [0, 1] using the chosen scientific colormap.
 */
export function evaluateScientificColormap(
  tNorm: number,
  colormap: ScientificColormap = 'viridis'
): [number, number, number] {
  const t = Math.max(0, Math.min(1, Number.isFinite(tNorm) ? tNorm : 0));
  const stops = COLORMAP_STOPS[colormap] ?? COLORMAP_STOPS.viridis;
  const scaled = t * (stops.length - 1);
  const idx = Math.min(Math.floor(scaled), stops.length - 2);
  const frac = scaled - idx;
  const c0 = stops[idx];
  const c1 = stops[idx + 1];
  return [
    c0[0] + (c1[0] - c0[0]) * frac,
    c0[1] + (c1[1] - c0[1]) * frac,
    c0[2] + (c1[2] - c0[2]) * frac,
  ];
}

/**
 * Return a CSS linear-gradient string for the scalar legend bar.
 */
export function getColormapCssGradient(colormap: ScientificColormap): string {
  const stops = COLORMAP_STOPS[colormap] ?? COLORMAP_STOPS.viridis;
  const cssStops = stops
    .map((rgb, idx) => {
      const pct = Math.round((idx / (stops.length - 1)) * 100);
      const r = Math.round(rgb[0] * 255);
      const g = Math.round(rgb[1] * 255);
      const b = Math.round(rgb[2] * 255);
      return `rgb(${r}, ${g}, ${b}) ${pct}%`;
    })
    .join(', ');
  return `linear-gradient(90deg, ${cssStops})`;
}

export interface ParsedVtuDataset {
  numberOfPoints: number;
  numberOfCells: number;
  points: number[][];
  cells: number[][];
  cellTypes: number[];
  pointScalars: Record<string, number[]>;
}

/**
 * Parse an ASCII VTK XML UnstructuredGrid (.vtu) document into typed vertex/cell/scalar arrays
 * suitable for Three.js BufferGeometry or vtk.js polydata pipelines.
 */
export function parseVtuXmlUnstructuredGrid(xmlText: string): ParsedVtuDataset {
  const pieceMatch = xmlText.match(
    /<Piece\s+NumberOfPoints="(\d+)"\s+NumberOfCells="(\d+)"/i
  );
  if (!pieceMatch) {
    throw new Error('Invalid VTU XML: missing <Piece NumberOfPoints="..." NumberOfCells="...">');
  }
  const numberOfPoints = parseInt(pieceMatch[1], 10);
  const numberOfCells = parseInt(pieceMatch[2], 10);

  const extractDataArrayNumbers = (sectionXml: string, nameAttr?: string): number[] => {
    const regex = nameAttr
      ? new RegExp(
          `<DataArray[^>]*Name="${nameAttr}"[^>]*>([\\s\\S]*?)<\\/DataArray>`,
          'i'
        )
      : /<DataArray[^>]*>([\s\S]*?)<\/DataArray>/i;
    const match = sectionXml.match(regex);
    if (!match) return [];
    const tokens = match[1].trim().split(/\s+/).filter(Boolean);
    return tokens.map((tok) => Number(tok));
  };

  const pointsSection = xmlText.match(/<Points>([\s\S]*?)<\/Points>/i)?.[1] ?? '';
  const rawPointCoords = extractDataArrayNumbers(pointsSection);
  const points: number[][] = [];
  for (let i = 0; i + 2 < rawPointCoords.length; i += 3) {
    points.push([rawPointCoords[i], rawPointCoords[i + 1], rawPointCoords[i + 2]]);
  }

  const cellsSection = xmlText.match(/<Cells>([\s\S]*?)<\/Cells>/i)?.[1] ?? '';
  const connectivity = extractDataArrayNumbers(cellsSection, 'connectivity');
  const offsets = extractDataArrayNumbers(cellsSection, 'offsets');
  const cellTypes = extractDataArrayNumbers(cellsSection, 'types');

  const cells: number[][] = [];
  let prevOffset = 0;
  for (const endOffset of offsets) {
    cells.push(connectivity.slice(prevOffset, endOffset));
    prevOffset = endOffset;
  }

  const pointScalars: Record<string, number[]> = {};
  const pointDataSection = xmlText.match(/<PointData[^>]*>([\s\S]*?)<\/PointData>/i)?.[1] ?? '';
  const dataArrayRegex =
    /<DataArray[^>]*Name="([^"]+)"[^>]*>([\s\S]*?)<\/DataArray>/gi;
  let arrMatch: RegExpExecArray | null = null;
  while ((arrMatch = dataArrayRegex.exec(pointDataSection)) !== null) {
    const arrayName = arrMatch[1];
    const values = arrMatch[2]
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((v) => Number(v));
    pointScalars[arrayName] = values;
  }

  return {
    numberOfPoints,
    numberOfCells,
    points,
    cells,
    cellTypes,
    pointScalars,
  };
}

export interface TetrahedralSliceGeometryData {
  /** Flat [x, y, z, ...] triangle vertex positions in display length units */
  positions: number[];
  /** Flat [r, g, b, ...] vertex colors in [0, 1] */
  colors: number[];
  /** Flat [x0, y0, z0, x1, y1, z1, ...] interior tetrahedral cut-edge segments */
  wireframePositions: number[];
  /** Number of intersected 3D tetrahedra */
  intersectedTetrahedra: number;
}

const TETRA_EDGES: ReadonlyArray<[number, number]> = [
  [0, 1],
  [0, 2],
  [0, 3],
  [1, 2],
  [1, 3],
  [2, 3],
];

/**
 * Exact Marching-Tetrahedra cross-section slicer:
 * Intersects all 3D tetrahedral cells (VTK_TETRA = 10) in a ParsedVtuDataset with an
 * axis-aligned plane (axis = 'x' | 'y' | 'z', coordinate = sliceCoordDisplay) and
 * returns triangle buffers and interior element wireframe segments.
 */
export function sliceVtuTetrahedraWithPlane(
  dataset: ParsedVtuDataset,
  axis: Exclude<ClipPlaneAxis, 'none'>,
  sliceCoordDisplay: number,
  lengthScaleFromM: number,
  minTempK: number,
  maxTempK: number,
  colormap: ScientificColormap
): TetrahedralSliceGeometryData {
  const positions: number[] = [];
  const colors: number[] = [];
  const wireframePositions: number[] = [];
  let intersectedTetrahedra = 0;

  const axisIdx = axis === 'x' ? 0 : axis === 'y' ? 1 : 2;
  const spanT = Math.max(maxTempK - minTempK, 1e-6);
  const tempArray =
    dataset.pointScalars['Temperature_K'] ??
    Object.values(dataset.pointScalars)[0] ??
    [];

  for (let cellIdx = 0; cellIdx < dataset.cells.length; cellIdx++) {
    // VTK_TETRA = 10
    if (dataset.cellTypes[cellIdx] !== 10) continue;
    const cell = dataset.cells[cellIdx];
    if (cell.length !== 4) continue;

    const ptsDisplay: Array<[number, number, number]> = [];
    const tempsK: number[] = [];
    const signedDists: number[] = [];

    for (let k = 0; k < 4; k++) {
      const vIdx = cell[k];
      const rawPt = dataset.points[vIdx];
      if (!rawPt) break;
      const px = rawPt[0] / lengthScaleFromM;
      const py = rawPt[1] / lengthScaleFromM;
      const pz = rawPt[2] / lengthScaleFromM;
      ptsDisplay.push([px, py, pz]);
      tempsK.push(tempArray[vIdx] ?? minTempK);
      const coord = axisIdx === 0 ? px : axisIdx === 1 ? py : pz;
      signedDists.push(coord - sliceCoordDisplay);
    }

    if (ptsDisplay.length !== 4) continue;

    // Collect edge intersections where signed distance crosses zero
    const intersections: Array<{ pt: [number, number, number]; tk: number }> = [];
    for (const [iA, iB] of TETRA_EDGES) {
      const sA = signedDists[iA];
      const sB = signedDists[iB];
      if ((sA < 0 && sB >= 0) || (sA >= 0 && sB < 0)) {
        const denom = sB - sA;
        const alpha = Math.abs(denom) > 1e-12 ? -sA / denom : 0.5;
        const pA = ptsDisplay[iA];
        const pB = ptsDisplay[iB];
        intersections.push({
          pt: [
            pA[0] + alpha * (pB[0] - pA[0]),
            pA[1] + alpha * (pB[1] - pA[1]),
            pA[2] + alpha * (pB[2] - pA[2]),
          ],
          tk: tempsK[iA] + alpha * (tempsK[iB] - tempsK[iA]),
        });
      }
    }

    if (intersections.length < 3) continue;
    intersectedTetrahedra += 1;

    // Sort polygon vertices angularly in the 2D slice plane so quads triangulate without bowties
    const uIdx = axisIdx === 0 ? 1 : 0;
    const vIdx = axisIdx === 2 ? 1 : 2;
    let cx = 0;
    let cy = 0;
    for (const item of intersections) {
      cx += item.pt[uIdx];
      cy += item.pt[vIdx];
    }
    cx /= intersections.length;
    cy /= intersections.length;

    intersections.sort(
      (a, b) =>
        Math.atan2(a.pt[vIdx] - cy, a.pt[uIdx] - cx) -
        Math.atan2(b.pt[vIdx] - cy, b.pt[uIdx] - cx)
    );

    const emitTri = (
      v0: { pt: [number, number, number]; tk: number },
      v1: { pt: [number, number, number]; tk: number },
      v2: { pt: [number, number, number]; tk: number }
    ) => {
      positions.push(
        v0.pt[0], v0.pt[1], v0.pt[2],
        v1.pt[0], v1.pt[1], v1.pt[2],
        v2.pt[0], v2.pt[1], v2.pt[2]
      );
      for (const vert of [v0, v1, v2]) {
        const [r, g, b] = evaluateScientificColormap((vert.tk - minTempK) / spanT, colormap);
        colors.push(r, g, b);
      }
    };

    emitTri(intersections[0], intersections[1], intersections[2]);
    if (intersections.length >= 4) {
      emitTri(intersections[0], intersections[2], intersections[3]);
    }

    for (let k = 0; k < intersections.length; k++) {
      const cur = intersections[k].pt;
      const nxt = intersections[(k + 1) % intersections.length].pt;
      wireframePositions.push(cur[0], cur[1], cur[2], nxt[0], nxt[1], nxt[2]);
    }
  }

  return {
    positions,
    colors,
    wireframePositions,
    intersectedTetrahedra,
  };
}
