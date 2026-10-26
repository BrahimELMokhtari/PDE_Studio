import { describe, expect, it } from 'vitest';
import {
  evaluateScientificColormap,
  getColormapCssGradient,
  parseVtuXmlUnstructuredGrid,
  sliceVtuTetrahedraWithPlane,
} from '../utils/vtuParser';

describe('Scientific Post-Processing Colormaps, VTU XML Parser & Marching-Tetrahedra Slicer (Phase 3)', () => {
  it('evaluates all 5 scientific colormaps within normalized [0, 1] RGB bounds', () => {
    const maps = ['viridis', 'inferno', 'coolwarm', 'plasma', 'jet'] as const;
    for (const cmap of maps) {
      for (const t of [0.0, 0.25, 0.5, 0.75, 1.0]) {
        const [r, g, b] = evaluateScientificColormap(t, cmap);
        expect(r).toBeGreaterThanOrEqual(0);
        expect(r).toBeLessThanOrEqual(1);
        expect(g).toBeGreaterThanOrEqual(0);
        expect(g).toBeLessThanOrEqual(1);
        expect(b).toBeGreaterThanOrEqual(0);
        expect(b).toBeLessThanOrEqual(1);
      }
      const gradient = getColormapCssGradient(cmap);
      expect(gradient).toContain('linear-gradient(90deg,');
    }
  });

  it('parses an ASCII VTK XML UnstructuredGrid (.vtu) dataset accurately', () => {
    const sampleVtu = `<?xml version="1.0"?>
<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">
  <UnstructuredGrid>
    <Piece NumberOfPoints="4" NumberOfCells="2">
      <Points>
        <DataArray type="Float32" Name="Points" NumberOfComponents="3" format="ascii">
          0.0 0.0 0.0
          1.0 0.0 0.0
          0.0 1.0 0.0
          0.0 0.0 1.0
        </DataArray>
      </Points>
      <Cells>
        <DataArray type="Int32" Name="connectivity" format="ascii">
          0 1 2 0 1 3
        </DataArray>
        <DataArray type="Int32" Name="offsets" format="ascii">
          3 6
        </DataArray>
        <DataArray type="UInt8" Name="types" format="ascii">
          5 5
        </DataArray>
      </Cells>
      <PointData Scalars="Temperature_K">
        <DataArray type="Float32" Name="Temperature_K" NumberOfComponents="1" format="ascii">
          300.0 350.0 375.0 400.0
        </DataArray>
      </PointData>
    </Piece>
  </UnstructuredGrid>
</VTKFile>`;

    const parsed = parseVtuXmlUnstructuredGrid(sampleVtu);
    expect(parsed.numberOfPoints).toBe(4);
    expect(parsed.numberOfCells).toBe(2);
    expect(parsed.points).toHaveLength(4);
    expect(parsed.points[1]).toEqual([1.0, 0.0, 0.0]);
    expect(parsed.cells).toEqual([
      [0, 1, 2],
      [0, 1, 3],
    ]);
    expect(parsed.cellTypes).toEqual([5, 5]);
    expect(parsed.pointScalars['Temperature_K']).toEqual([300.0, 350.0, 375.0, 400.0]);
  });

  it('computes exact Marching-Tetrahedra cross-section triangles on a 3D VTK_TETRA cell', () => {
    const tetraVtu = `<?xml version="1.0"?>
<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">
  <UnstructuredGrid>
    <Piece NumberOfPoints="4" NumberOfCells="1">
      <Points>
        <DataArray type="Float32" Name="Points" NumberOfComponents="3" format="ascii">
          0.0 0.0 0.0
          1.0 0.0 0.0
          0.0 1.0 0.0
          0.0 0.0 1.0
        </DataArray>
      </Points>
      <Cells>
        <DataArray type="Int32" Name="connectivity" format="ascii">
          0 1 2 3
        </DataArray>
        <DataArray type="Int32" Name="offsets" format="ascii">
          4
        </DataArray>
        <DataArray type="UInt8" Name="types" format="ascii">
          10
        </DataArray>
      </Cells>
      <PointData Scalars="Temperature_K">
        <DataArray type="Float32" Name="Temperature_K" NumberOfComponents="1" format="ascii">
          300.0 400.0 300.0 300.0
        </DataArray>
      </PointData>
    </Piece>
  </UnstructuredGrid>
</VTKFile>`;

    const dataset = parseVtuXmlUnstructuredGrid(tetraVtu);
    const slice = sliceVtuTetrahedraWithPlane(
      dataset,
      'x',
      0.5,
      1.0,
      300.0,
      400.0,
      'viridis'
    );
    expect(slice.intersectedTetrahedra).toBe(1);
    // 1 triangle = 3 vertices * 3 floats = 9 floats
    expect(slice.positions.length).toBe(9);
    expect(slice.colors.length).toBe(9);
    expect(slice.wireframePositions.length).toBe(18);
  });
});
