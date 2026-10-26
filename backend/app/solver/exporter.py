"""Scientific result exporters for VTK/VTU XML UnstructuredGrid and CSV datasets."""

from __future__ import annotations

import csv
import io

import ngsolve as ngs

from app.schemas.simulation_schema import SimulationResultSummary


def export_ngsolve_volume_vtu_bytes(
    mesh: ngs.Mesh,
    gfu_temp_k: ngs.GridFunction,
    heat_flux_cf: ngs.CoefficientFunction,
) -> bytes:
    """Export the 3D tetrahedral volume mesh, nodal temperatures (K), and cell heat flux vectors (W/m^2)
    to a standards-compliant ASCII VTK XML UnstructuredGrid (.vtu) compatible with ParaView and vtk.js.
    """
    num_pts = int(mesh.nv)
    pts_lines: list[str] = []
    temp_k_vals: list[str] = []

    for i, vtx in enumerate(mesh.vertices):
        pt = vtx.point
        pts_lines.append(f"{float(pt[0]):.6f} {float(pt[1]):.6f} {float(pt[2]):.6f}")
        tk = float(gfu_temp_k.vec[i])
        temp_k_vals.append(f"{tk:.5f}")

    conn_list: list[str] = []
    offsets_list: list[str] = []
    types_list: list[str] = []
    cell_flux_list: list[str] = []

    offset = 0
    num_cells = 0
    for el in mesh.Elements(ngs.VOL):
        v_nrs = [int(v_id.nr) for v_id in el.vertices]
        if len(v_nrs) != 4:
            continue
        num_cells += 1
        conn_list.append(f"{v_nrs[0]} {v_nrs[1]} {v_nrs[2]} {v_nrs[3]}")
        offset += 4
        offsets_list.append(str(offset))
        types_list.append("10")  # VTK_TETRA = 10

        # Evaluate heat flux vector at element centroid
        try:
            p0 = mesh.vertices[v_nrs[0]].point
            p1 = mesh.vertices[v_nrs[1]].point
            p2 = mesh.vertices[v_nrs[2]].point
            p3 = mesh.vertices[v_nrs[3]].point
            cx = 0.25 * (float(p0[0]) + float(p1[0]) + float(p2[0]) + float(p3[0]))
            cy = 0.25 * (float(p0[1]) + float(p1[1]) + float(p2[1]) + float(p3[1]))
            cz = 0.25 * (float(p0[2]) + float(p1[2]) + float(p2[2]) + float(p3[2]))
            mip = mesh(cx, cy, cz)
            q_val = heat_flux_cf(mip)
            cell_flux_list.append(
                f"{float(q_val[0]):.4f} {float(q_val[1]):.4f} {float(q_val[2]):.4f}"
            )
        except Exception:
            cell_flux_list.append("0.0 0.0 0.0")

    pts_str = "\n          ".join(pts_lines)
    temp_k_str = " ".join(temp_k_vals)
    conn_str = " ".join(conn_list)
    offsets_str = " ".join(offsets_list)
    types_str = " ".join(types_list)
    flux_str = "\n          ".join(cell_flux_list)

    xml_content = f"""<?xml version="1.0"?>
<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">
  <UnstructuredGrid>
    <Piece NumberOfPoints="{num_pts}" NumberOfCells="{num_cells}">
      <Points>
        <DataArray type="Float32" Name="Points" NumberOfComponents="3" format="ascii">
          {pts_str}
        </DataArray>
      </Points>
      <Cells>
        <DataArray type="Int32" Name="connectivity" format="ascii">
          {conn_str}
        </DataArray>
        <DataArray type="Int32" Name="offsets" format="ascii">
          {offsets_str}
        </DataArray>
        <DataArray type="UInt8" Name="types" format="ascii">
          {types_str}
        </DataArray>
      </Cells>
      <PointData Scalars="Temperature_K">
        <DataArray type="Float32" Name="Temperature_K" NumberOfComponents="1" format="ascii">
          {temp_k_str}
        </DataArray>
      </PointData>
      <CellData Vectors="HeatFlux_W_m2">
        <DataArray type="Float32" Name="HeatFlux_W_m2" NumberOfComponents="3" format="ascii">
          {flux_str}
        </DataArray>
      </CellData>
    </Piece>
  </UnstructuredGrid>
</VTKFile>
"""
    return xml_content.encode("utf-8")


def export_surface_vtu_from_summary(result: SimulationResultSummary) -> bytes:
    """Generate a valid ASCII VTK XML UnstructuredGrid (.vtu) from a SimulationResultSummary surface mesh."""
    sm = result.surface_mesh
    num_pts = len(sm.vertices)
    num_cells = len(sm.triangles)

    pts_str = "\n          ".join(
        f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}" for v in sm.vertices
    )
    temp_k_str = " ".join(f"{t:.5f}" for t in sm.vertex_temperatures_k)
    temp_disp_str = " ".join(f"{t:.5f}" for t in sm.vertex_temperatures_display)

    conn_list: list[str] = []
    offsets_list: list[str] = []
    types_list: list[str] = []
    face_id_map = {"X_MIN": 0, "X_MAX": 1, "Y_MIN": 2, "Y_MAX": 3, "Z_MIN": 4, "Z_MAX": 5}
    face_ids_list: list[str] = []

    offset = 0
    for idx, tri in enumerate(sm.triangles):
        conn_list.append(f"{tri[0]} {tri[1]} {tri[2]}")
        offset += 3
        offsets_list.append(str(offset))
        types_list.append("5")  # VTK_TRIANGLE = 5
        fname = sm.triangle_face_ids[idx] if idx < len(sm.triangle_face_ids) else "X_MIN"
        face_ids_list.append(str(face_id_map.get(fname, 0)))

    conn_str = " ".join(conn_list)
    offsets_str = " ".join(offsets_list)
    types_str = " ".join(types_list)
    face_ids_str = " ".join(face_ids_list)

    xml_content = f"""<?xml version="1.0"?>
<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">
  <UnstructuredGrid>
    <Piece NumberOfPoints="{num_pts}" NumberOfCells="{num_cells}">
      <Points>
        <DataArray type="Float32" Name="Points" NumberOfComponents="3" format="ascii">
          {pts_str}
        </DataArray>
      </Points>
      <Cells>
        <DataArray type="Int32" Name="connectivity" format="ascii">
          {conn_str}
        </DataArray>
        <DataArray type="Int32" Name="offsets" format="ascii">
          {offsets_str}
        </DataArray>
        <DataArray type="UInt8" Name="types" format="ascii">
          {types_str}
        </DataArray>
      </Cells>
      <PointData Scalars="Temperature_K">
        <DataArray type="Float32" Name="Temperature_K" NumberOfComponents="1" format="ascii">
          {temp_k_str}
        </DataArray>
        <DataArray type="Float32" Name="Temperature_{result.temperature_unit}" NumberOfComponents="1" format="ascii">
          {temp_disp_str}
        </DataArray>
      </PointData>
      <CellData Scalars="BoundaryFaceId">
        <DataArray type="Int32" Name="BoundaryFaceId" NumberOfComponents="1" format="ascii">
          {face_ids_str}
        </DataArray>
      </CellData>
    </Piece>
  </UnstructuredGrid>
</VTKFile>
"""
    return xml_content.encode("utf-8")


def export_nodal_csv_bytes(result: SimulationResultSummary) -> bytes:
    """Export nodal coordinates and computed temperatures to CSV format."""
    sm = result.surface_mesh
    node_faces: dict[int, set[str]] = {}
    for idx, tri in enumerate(sm.triangles):
        fname = sm.triangle_face_ids[idx] if idx < len(sm.triangle_face_ids) else ""
        if fname:
            for v_idx in tri:
                node_faces.setdefault(v_idx, set()).add(fname)

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "node_id",
            f"x ({result.length_unit})",
            f"y ({result.length_unit})",
            f"z ({result.length_unit})",
            "temperature_k",
            f"temperature ({result.temperature_unit})",
            "boundary_faces",
        ]
    )

    for i, coords in enumerate(sm.vertices):
        tk = sm.vertex_temperatures_k[i] if i < len(sm.vertex_temperatures_k) else 0.0
        td = (
            sm.vertex_temperatures_display[i]
            if i < len(sm.vertex_temperatures_display)
            else 0.0
        )
        faces_str = "|".join(sorted(node_faces.get(i, set()))) or "INTERIOR"
        writer.writerow(
            [
                i,
                f"{coords[0]:.6f}",
                f"{coords[1]:.6f}",
                f"{coords[2]:.6f}",
                f"{tk:.5f}",
                f"{td:.5f}",
                faces_str,
            ]
        )

    return buf.getvalue().encode("utf-8")


def export_boundary_csv_bytes(result: SimulationResultSummary) -> bytes:
    """Export per-face boundary temperatures, surface areas, and net outward heat flow rates to CSV format."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "face_id",
            "bc_type",
            "area_m2",
            "min_temperature_k",
            "max_temperature_k",
            "mean_temperature_k",
            f"min_temperature ({result.temperature_unit})",
            f"max_temperature ({result.temperature_unit})",
            f"mean_temperature ({result.temperature_unit})",
            "net_outward_heat_rate_w",
        ]
    )

    for fname, bstat in result.boundary_stats.items():
        writer.writerow(
            [
                fname,
                bstat.bc_type,
                f"{bstat.area_m2:.6f}",
                f"{bstat.min_temperature_k:.4f}",
                f"{bstat.max_temperature_k:.4f}",
                f"{bstat.mean_temperature_k:.4f}",
                f"{bstat.min_temperature_display:.4f}",
                f"{bstat.max_temperature_display:.4f}",
                f"{bstat.mean_temperature_display:.4f}",
                f"{bstat.net_outward_heat_rate_w:.4f}",
            ]
        )

    return buf.getvalue().encode("utf-8")
