/**
 * Interactive 3D CAD/CAE & Scientific FEM Post-Processing Viewport built on Three.js
 *
 * Features:
 * - Parametric rectangular cuboid with 6 semantic face meshes (X_MIN..Z_MAX)
 * - Never relies on unstable triangle indices for boundary identification
 * - Phase 2/3 FEM 3D Temperature Contour Mode: renders the NGSolve tetrahedral
 *   boundary surface mesh with multi-colormap interpolation (Viridis, Inferno, CoolWarm, Plasma, Jet)
 * - Interactive 3D Cross-Sectional Slicing & Clipping Plane (X, Y, Z axes with interior contour slice)
 * - Interactive Colorbar Legend (T_min .. T_mean .. T_max) & Mesh Quality Statistics
 */

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  ALL_FACE_IDS,
  BoundaryConditionType,
  CameraPreset,
  CanonicalSimulationModel,
  FaceId,
  SimulationResultSummary,
} from '../types/model';
import {
  getSemanticFacePlaneTransform,
  resolveSemanticFaceFromHit,
  SEMANTIC_FACE_DESCRIPTORS,
} from '../utils/semanticFaces';
import {
  ClipPlaneAxis,
  evaluateScientificColormap,
  getColormapCssGradient,
  ParsedVtuDataset,
  ScientificColormap,
  sliceVtuTetrahedraWithPlane,
} from '../utils/vtuParser';

export interface Viewport3DProps {
  model: CanonicalSimulationModel;
  simulationResult?: SimulationResultSummary | null;
  vtuDataset?: ParsedVtuDataset | null;
  showContourField?: boolean;
  onToggleContourField?: () => void;
  selectedFace: FaceId;
  hoveredFace: FaceId | null;
  onSelectFace: (faceId: FaceId) => void;
  onHoverFace: (faceId: FaceId | null) => void;
  showGrid: boolean;
  showAxes: boolean;
  showMeshLines: boolean;
  showBcColors: boolean;
  cameraPresetTrigger: { preset: CameraPreset; seq: number };
  onToggleGrid: () => void;
  onToggleAxes: () => void;
  onToggleMeshLines: () => void;
  onToggleBcColors: () => void;
  onTriggerCameraPreset: (preset: CameraPreset) => void;
}

const BC_FACE_COLORS: Record<BoundaryConditionType, number> = {
  dirichlet: 0xe05d44,
  robin: 0x2b8cbe,
  neumann: 0x9b59b6,
  insulated: 0x4b5b6b,
};

const NEUTRAL_CAD_COLOR = 0x56697a;
const HOVER_COLOR = 0x38bdf8;
const SELECTED_COLOR = 0xf59e0b;

function buildFaceSubdivisionGridGeometry(
  width: number,
  height: number,
  divU: number,
  divV: number
): THREE.BufferGeometry {
  const positions: number[] = [];
  const halfW = width / 2;
  const halfH = height / 2;
  const safeU = Math.max(1, Math.min(80, Math.floor(divU)));
  const safeV = Math.max(1, Math.min(80, Math.floor(divV)));

  for (let i = 1; i < safeU; i++) {
    const x = -halfW + (i / safeU) * width;
    positions.push(x, -halfH, 0.001, x, halfH, 0.001);
  }
  for (let j = 1; j < safeV; j++) {
    const y = -halfH + (j / safeV) * height;
    positions.push(-halfW, y, 0.001, halfW, y, 0.001);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  return geometry;
}

/**
 * Inverse-distance weighted temperature interpolation from boundary/centerline nodes
 * for rendering an interior 2D cross-sectional slice plane in 3D WebGL.
 */
function buildCrossSectionSliceMesh(
  axis: Exclude<ClipPlaneAxis, 'none'>,
  sliceCoord: number,
  dims: { lx: number; ly: number; lz: number },
  center: { cx: number; cy: number; cz: number },
  simulationResult: SimulationResultSummary,
  colormap: ScientificColormap
): THREE.Group {
  const group = new THREE.Group();
  const surf = simulationResult.surface_mesh;
  const minT = simulationResult.min_temperature_k;
  const maxT = simulationResult.max_temperature_k;
  const spanT = Math.max(maxT - minT, 1e-6);

  const gridRes = 18;
  const posArr: number[] = [];
  const colArr: number[] = [];

  const sampleTempAtPoint = (wx: number, wy: number, wz: number): number => {
    let weightedSum = 0;
    let weightTotal = 0;
    const stride = Math.max(1, Math.floor(surf.vertices.length / 180));
    for (let i = 0; i < surf.vertices.length; i += stride) {
      const v = surf.vertices[i];
      const tk = surf.vertex_temperatures_k[i] ?? minT;
      const d2 =
        (wx - v[0]) * (wx - v[0]) +
        (wy - v[1]) * (wy - v[1]) +
        (wz - v[2]) * (wz - v[2]);
      if (d2 < 1e-9) return tk;
      const w = 1.0 / (d2 * d2 + 1e-6);
      weightedSum += w * tk;
      weightTotal += w;
    }
    return weightTotal > 0 ? weightedSum / weightTotal : simulationResult.mean_temperature_k;
  };

  const uSpan = axis === 'x' ? dims.ly : dims.lx;
  const vSpan = axis === 'z' ? dims.ly : dims.lz;

  const toWorld = (u: number, v: number): [number, number, number] => {
    if (axis === 'x') return [sliceCoord, center.cy + u, center.cz + v];
    if (axis === 'y') return [center.cx + u, sliceCoord, center.cz + v];
    return [center.cx + u, center.cy + v, sliceCoord];
  };

  for (let iu = 0; iu < gridRes; iu++) {
    const u0 = -uSpan / 2 + (iu / gridRes) * uSpan;
    const u1 = -uSpan / 2 + ((iu + 1) / gridRes) * uSpan;
    for (let iv = 0; iv < gridRes; iv++) {
      const v0 = -vSpan / 2 + (iv / gridRes) * vSpan;
      const v1 = -vSpan / 2 + ((iv + 1) / gridRes) * vSpan;

      const p00 = toWorld(u0, v0);
      const p10 = toWorld(u1, v0);
      const p11 = toWorld(u1, v1);
      const p01 = toWorld(u0, v1);

      const corners = [p00, p10, p11, p00, p11, p01];
      for (const pt of corners) {
        posArr.push(pt[0], pt[1], pt[2]);
        const tk = sampleTempAtPoint(pt[0], pt[1], pt[2]);
        const [r, g, b] = evaluateScientificColormap((tk - minT) / spanT, colormap);
        colArr.push(r, g, b);
      }
    }
  }

  const sliceGeom = new THREE.BufferGeometry();
  sliceGeom.setAttribute('position', new THREE.Float32BufferAttribute(posArr, 3));
  sliceGeom.setAttribute('color', new THREE.Float32BufferAttribute(colArr, 3));
  sliceGeom.computeVertexNormals();

  const sliceMat = new THREE.MeshBasicMaterial({
    vertexColors: true,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.94,
  });
  group.add(new THREE.Mesh(sliceGeom, sliceMat));

  // Add bright cyan border around the active cross-section plane
  const b0 = toWorld(-uSpan / 2, -vSpan / 2);
  const b1 = toWorld(uSpan / 2, -vSpan / 2);
  const b2 = toWorld(uSpan / 2, vSpan / 2);
  const b3 = toWorld(-uSpan / 2, vSpan / 2);
  const borderPts = [
    ...b0, ...b1,
    ...b1, ...b2,
    ...b2, ...b3,
    ...b3, ...b0,
  ];
  const borderGeom = new THREE.BufferGeometry();
  borderGeom.setAttribute('position', new THREE.Float32BufferAttribute(borderPts, 3));
  const borderMat = new THREE.LineBasicMaterial({ color: 0x38bdf8 });
  group.add(new THREE.LineSegments(borderGeom, borderMat));

  return group;
}

export const Viewport3D: React.FC<Viewport3DProps> = ({
  model,
  simulationResult,
  vtuDataset = null,
  showContourField = false,
  onToggleContourField,
  selectedFace,
  hoveredFace,
  onSelectFace,
  onHoverFace,
  showGrid,
  showAxes,
  showMeshLines,
  showBcColors,
  cameraPresetTrigger,
  onToggleGrid,
  onToggleAxes,
  onToggleMeshLines,
  onToggleBcColors,
  onTriggerCameraPreset,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cuboidGroupRef = useRef<THREE.Group | null>(null);
  const faceMeshesRef = useRef<Record<FaceId, THREE.Mesh> | null>(null);
  const gridHelperRef = useRef<THREE.GridHelper | null>(null);
  const axesHelperRef = useRef<THREE.AxesHelper | null>(null);

  // Phase 3 Scientific Post-Processing State: Colormap & 3D Cross-Section Clipping
  const [colormap, setColormap] = useState<ScientificColormap>('viridis');
  const [clipAxis, setClipAxis] = useState<ClipPlaneAxis>('none');
  const [clipOffsetPct, setClipOffsetPct] = useState<number>(0); // -45 to +45 (%)
  const [invertClip, setInvertClip] = useState<boolean>(false);

  const onSelectFaceRef = useRef(onSelectFace);
  const onHoverFaceRef = useRef(onHoverFace);
  onSelectFaceRef.current = onSelectFace;
  onHoverFaceRef.current = onHoverFace;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0c1219);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.01, 2000);
    camera.position.set(2.4, 1.8, 2.4);
    cameraRef.current = camera;

    let renderer: THREE.WebGLRenderer | null = null;
    try {
      const probeCanvas = document.createElement('canvas');
      const gl =
        probeCanvas.getContext('webgl2') ||
        probeCanvas.getContext('webgl') ||
        probeCanvas.getContext('experimental-webgl');
      if (!gl) {
        return;
      }
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
      renderer.localClippingEnabled = true;
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      container.innerHTML = '';
      container.appendChild(renderer.domElement);
      rendererRef.current = renderer;
    } catch {
      return;
    }

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 0, 0);
    controlsRef.current = controls;

    const ambientLight = new THREE.AmbientLight(0xdbeafe, 0.78);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 0.92);
    keyLight.position.set(6, 10, 8);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x93c5fd, 0.45);
    fillLight.position.set(-7, -4, -6);
    scene.add(fillLight);

    const gridHelper = new THREE.GridHelper(6, 24, 0x334155, 0x1e293b);
    gridHelper.position.y = -0.002;
    scene.add(gridHelper);
    gridHelperRef.current = gridHelper;

    const axesHelper = new THREE.AxesHelper(1.5);
    scene.add(axesHelper);
    axesHelperRef.current = axesHelper;

    const cuboidGroup = new THREE.Group();
    cuboidGroup.name = 'ParametricCuboidGroup';
    scene.add(cuboidGroup);
    cuboidGroupRef.current = cuboidGroup;

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let pointerDownPos = { x: 0, y: 0 };

    const getSemanticHitFace = (event: MouseEvent): FaceId | null => {
      if (!renderer || !faceMeshesRef.current || !cuboidGroupRef.current) return null;
      const rect = renderer.domElement.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return null;

      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(pointer, camera);
      const meshes = Object.values(faceMeshesRef.current);
      const intersects = raycaster.intersectObjects(meshes, false);

      if (intersects.length === 0) return null;
      const hit = intersects[0];

      const localPoint = cuboidGroupRef.current.worldToLocal(hit.point.clone());
      return resolveSemanticFaceFromHit(
        hit.object.userData as Record<string, unknown>,
        { x: localPoint.x, y: localPoint.y, z: localPoint.z }
      );
    };

    const handlePointerMove = (event: MouseEvent) => {
      const faceId = getSemanticHitFace(event);
      onHoverFaceRef.current(faceId);
      if (renderer) {
        renderer.domElement.style.cursor = faceId ? 'pointer' : 'grab';
      }
    };

    const handlePointerDown = (event: MouseEvent) => {
      pointerDownPos = { x: event.clientX, y: event.clientY };
    };

    const handlePointerUp = (event: MouseEvent) => {
      const dist = Math.hypot(
        event.clientX - pointerDownPos.x,
        event.clientY - pointerDownPos.y
      );
      if (dist < 5 && event.button === 0) {
        const faceId = getSemanticHitFace(event);
        if (faceId) {
          onSelectFaceRef.current(faceId);
        }
      }
    };

    const handlePointerLeave = () => {
      onHoverFaceRef.current(null);
    };

    const domElem = renderer.domElement;
    domElem.addEventListener('pointermove', handlePointerMove);
    domElem.addEventListener('pointerdown', handlePointerDown);
    domElem.addEventListener('pointerup', handlePointerUp);
    domElem.addEventListener('pointerleave', handlePointerLeave);

    const handleResize = () => {
      if (!container || !renderer || !camera) return;
      const w = container.clientWidth || 800;
      const h = container.clientHeight || 600;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    const resizeObserver =
      typeof ResizeObserver !== 'undefined' ? new ResizeObserver(handleResize) : null;
    resizeObserver?.observe(container);
    window.addEventListener('resize', handleResize);

    let animFrameId = 0;
    const animate = () => {
      animFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer?.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animFrameId);
      resizeObserver?.disconnect();
      window.removeEventListener('resize', handleResize);
      domElem.removeEventListener('pointermove', handlePointerMove);
      domElem.removeEventListener('pointerdown', handlePointerDown);
      domElem.removeEventListener('pointerup', handlePointerUp);
      domElem.removeEventListener('pointerleave', handlePointerLeave);
      controls.dispose();
      renderer?.dispose();
    };
  }, []);

  useEffect(() => {
    if (gridHelperRef.current) {
      gridHelperRef.current.visible = showGrid;
    }
    if (axesHelperRef.current) {
      axesHelperRef.current.visible = showAxes;
    }
  }, [showGrid, showAxes]);

  // Rebuild 3D Scene Geometry (CAD Boundary Mode OR Solved 3D FEM Temperature Contour Mode)
  useEffect(() => {
    const cuboidGroup = cuboidGroupRef.current;
    if (!cuboidGroup) return;

    while (cuboidGroup.children.length > 0) {
      cuboidGroup.remove(cuboidGroup.children[0]);
    }

    const { dimensions, position, rotation_deg } = model.geometry;
    const { divisions } = model.mesh;

    const lx = Math.max(0.01, Number(dimensions.length_x) || 1);
    const ly = Math.max(0.01, Number(dimensions.length_y) || 1);
    const lz = Math.max(0.01, Number(dimensions.length_z) || 1);
    const safeDims = { length_x: lx, length_y: ly, length_z: lz };

    // When rendering the FEM contour mesh, NGSolve vertices are in world coordinates (scaled to model length units)
    if (showContourField && simulationResult?.surface_mesh) {
      cuboidGroup.position.set(0, 0, 0);
      cuboidGroup.rotation.set(0, 0, 0);

      const surf = simulationResult.surface_mesh;
      const minT = simulationResult.min_temperature_k;
      const maxT = simulationResult.max_temperature_k;
      const spanT = Math.max(maxT - minT, 1e-6);

      // Configure optional Three.js local clipping plane
      const activeClipPlanes: THREE.Plane[] = [];
      const cx = Number(position.x) || 0;
      const cy = Number(position.y) || 0;
      const cz = Number(position.z) || 0;
      let sliceWorldCoord = 0;

      if (clipAxis !== 'none') {
        const span = clipAxis === 'x' ? lx : clipAxis === 'y' ? ly : lz;
        const centerCoord = clipAxis === 'x' ? cx : clipAxis === 'y' ? cy : cz;
        sliceWorldCoord = centerCoord + (clipOffsetPct / 100) * span;
        const sign = invertClip ? 1 : -1;
        const normal =
          clipAxis === 'x'
            ? new THREE.Vector3(sign, 0, 0)
            : clipAxis === 'y'
            ? new THREE.Vector3(0, sign, 0)
            : new THREE.Vector3(0, 0, sign);
        // Plane equation: normal.dot(p) + constant >= 0
        const constant = -sign * sliceWorldCoord;
        activeClipPlanes.push(new THREE.Plane(normal, constant));
      }

      const posArr: number[] = [];
      const colArr: number[] = [];
      const wireArr: number[] = [];

      for (const tri of surf.triangles) {
        const v0 = surf.vertices[tri[0]];
        const v1 = surf.vertices[tri[1]];
        const v2 = surf.vertices[tri[2]];
        if (!v0 || !v1 || !v2) continue;

        posArr.push(v0[0], v0[1], v0[2], v1[0], v1[1], v1[2], v2[0], v2[1], v2[2]);

        for (const vIdx of tri) {
          const tk = surf.vertex_temperatures_k[vIdx] ?? minT;
          const [r, g, b] = evaluateScientificColormap((tk - minT) / spanT, colormap);
          colArr.push(r, g, b);
        }

        if (showMeshLines) {
          wireArr.push(
            v0[0], v0[1], v0[2], v1[0], v1[1], v1[2],
            v1[0], v1[1], v1[2], v2[0], v2[1], v2[2],
            v2[0], v2[1], v2[2], v0[0], v0[1], v0[2]
          );
        }
      }

      const contourGeom = new THREE.BufferGeometry();
      contourGeom.setAttribute('position', new THREE.Float32BufferAttribute(posArr, 3));
      contourGeom.setAttribute('color', new THREE.Float32BufferAttribute(colArr, 3));
      contourGeom.computeVertexNormals();

      const contourMat = new THREE.MeshBasicMaterial({
        vertexColors: true,
        side: THREE.DoubleSide,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
        clippingPlanes: activeClipPlanes,
      });

      const contourMesh = new THREE.Mesh(contourGeom, contourMat);
      cuboidGroup.add(contourMesh);

      if (showMeshLines && wireArr.length > 0) {
        const wireGeom = new THREE.BufferGeometry();
        wireGeom.setAttribute('position', new THREE.Float32BufferAttribute(wireArr, 3));
        const wireMat = new THREE.LineBasicMaterial({
          color: 0x0f172a,
          transparent: true,
          opacity: 0.45,
          clippingPlanes: activeClipPlanes,
        });
        cuboidGroup.add(new THREE.LineSegments(wireGeom, wireMat));
      }

      if (clipAxis !== 'none') {
        const lengthScaleToM =
          simulationResult.length_unit === 'mm'
            ? 0.001
            : simulationResult.length_unit === 'cm'
            ? 0.01
            : 1.0;

        let addedExactVtuSlice = false;
        if (vtuDataset && vtuDataset.cellTypes.includes(10)) {
          const sliced = sliceVtuTetrahedraWithPlane(
            vtuDataset,
            clipAxis,
            sliceWorldCoord,
            lengthScaleToM,
            minT,
            maxT,
            colormap
          );
          if (sliced.positions.length > 0) {
            const vtuSliceGroup = new THREE.Group();
            const sliceGeom = new THREE.BufferGeometry();
            sliceGeom.setAttribute(
              'position',
              new THREE.Float32BufferAttribute(sliced.positions, 3)
            );
            sliceGeom.setAttribute(
              'color',
              new THREE.Float32BufferAttribute(sliced.colors, 3)
            );
            sliceGeom.computeVertexNormals();
            const sliceMat = new THREE.MeshBasicMaterial({
              vertexColors: true,
              side: THREE.DoubleSide,
            });
            vtuSliceGroup.add(new THREE.Mesh(sliceGeom, sliceMat));

            if (showMeshLines && sliced.wireframePositions.length > 0) {
              const cutWireGeom = new THREE.BufferGeometry();
              cutWireGeom.setAttribute(
                'position',
                new THREE.Float32BufferAttribute(sliced.wireframePositions, 3)
              );
              const cutWireMat = new THREE.LineBasicMaterial({
                color: 0x38bdf8,
                transparent: true,
                opacity: 0.65,
              });
              vtuSliceGroup.add(new THREE.LineSegments(cutWireGeom, cutWireMat));
            }
            cuboidGroup.add(vtuSliceGroup);
            addedExactVtuSlice = true;
          }
        }

        if (!addedExactVtuSlice) {
          const sliceGroup = buildCrossSectionSliceMesh(
            clipAxis,
            sliceWorldCoord,
            { lx, ly, lz },
            { cx, cy, cz },
            simulationResult,
            colormap
          );
          cuboidGroup.add(sliceGroup);
        }
      }

      faceMeshesRef.current = null;
      return;
    }

    // Standard CAD/CAE Semantic Face Mode
    cuboidGroup.position.set(
      Number(position.x) || 0,
      Number(position.y) || 0,
      Number(position.z) || 0
    );
    cuboidGroup.rotation.set(
      THREE.MathUtils.degToRad(Number(rotation_deg.x) || 0),
      THREE.MathUtils.degToRad(Number(rotation_deg.y) || 0),
      THREE.MathUtils.degToRad(Number(rotation_deg.z) || 0)
    );

    const newFaceMeshes = {} as Record<FaceId, THREE.Mesh>;

    for (const faceId of ALL_FACE_IDS) {
      const planeInfo = getSemanticFacePlaneTransform(faceId, safeDims, divisions);
      const bc = model.boundary_conditions[faceId];
      const isSelected = selectedFace === faceId;
      const isHovered = hoveredFace === faceId;

      let baseColor = showBcColors ? BC_FACE_COLORS[bc.type] : NEUTRAL_CAD_COLOR;
      let emissiveColor = 0x000000;
      let emissiveIntensity = 0.0;

      if (isSelected) {
        baseColor = SELECTED_COLOR;
        emissiveColor = SELECTED_COLOR;
        emissiveIntensity = 0.28;
      } else if (isHovered) {
        baseColor = HOVER_COLOR;
        emissiveColor = HOVER_COLOR;
        emissiveIntensity = 0.22;
      }

      const planeGeom = new THREE.PlaneGeometry(planeInfo.planeWidth, planeInfo.planeHeight);
      const mat = new THREE.MeshStandardMaterial({
        color: baseColor,
        emissive: emissiveColor,
        emissiveIntensity,
        roughness: 0.42,
        metalness: 0.18,
        side: THREE.DoubleSide,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      });

      const faceMesh = new THREE.Mesh(planeGeom, mat);
      faceMesh.name = `SemanticFace_${faceId}`;
      faceMesh.userData = {
        faceId,
        outwardNormal: planeInfo.outwardNormal,
        surfaceArea: planeInfo.area,
      };

      faceMesh.position.set(planeInfo.center.x, planeInfo.center.y, planeInfo.center.z);
      faceMesh.rotation.set(
        planeInfo.eulerRotationRad.x,
        planeInfo.eulerRotationRad.y,
        planeInfo.eulerRotationRad.z
      );

      if (showMeshLines) {
        const subGridGeom = buildFaceSubdivisionGridGeometry(
          planeInfo.planeWidth,
          planeInfo.planeHeight,
          planeInfo.gridDivisionsU,
          planeInfo.gridDivisionsV
        );
        const subGridMat = new THREE.LineBasicMaterial({
          color: isSelected ? 0xfef08a : 0x94a3b8,
          transparent: true,
          opacity: isSelected ? 0.85 : 0.38,
        });
        faceMesh.add(new THREE.LineSegments(subGridGeom, subGridMat));
      }

      if (isSelected || isHovered) {
        const borderEdges = new THREE.EdgesGeometry(planeGeom);
        const borderMat = new THREE.LineBasicMaterial({
          color: isSelected ? 0xfde047 : 0x7dd3fc,
        });
        const borderSegments = new THREE.LineSegments(borderEdges, borderMat);
        borderSegments.position.z = 0.002;
        faceMesh.add(borderSegments);
      }

      if (isSelected) {
        const maxDim = Math.max(lx, ly, lz);
        const arrowLen = Math.max(0.25, maxDim * 0.32);
        const dir = new THREE.Vector3(
          planeInfo.outwardNormal.x,
          planeInfo.outwardNormal.y,
          planeInfo.outwardNormal.z
        ).normalize();
        const origin = new THREE.Vector3(
          planeInfo.center.x,
          planeInfo.center.y,
          planeInfo.center.z
        );
        const arrowHelper = new THREE.ArrowHelper(
          dir,
          origin,
          arrowLen,
          0xf59e0b,
          arrowLen * 0.28,
          arrowLen * 0.16
        );
        cuboidGroup.add(arrowHelper);
      }

      cuboidGroup.add(faceMesh);
      newFaceMeshes[faceId] = faceMesh;
    }

    const outerBoxGeom = new THREE.BoxGeometry(lx, ly, lz);
    const outerEdgesGeom = new THREE.EdgesGeometry(outerBoxGeom);
    const outerEdgesMat = new THREE.LineBasicMaterial({ color: 0xe2e8f0 });
    cuboidGroup.add(new THREE.LineSegments(outerEdgesGeom, outerEdgesMat));

    faceMeshesRef.current = newFaceMeshes;
  }, [
    model,
    selectedFace,
    hoveredFace,
    showMeshLines,
    showBcColors,
    showContourField,
    simulationResult,
    vtuDataset,
    colormap,
    clipAxis,
    clipOffsetPct,
    invertClip,
  ]);

  useEffect(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    const { dimensions, position } = model.geometry;
    const maxDim = Math.max(
      dimensions.length_x || 1,
      dimensions.length_y || 1,
      dimensions.length_z || 1,
      0.5
    );
    const dist = maxDim * 2.35;
    const cx = Number(position.x) || 0;
    const cy = Number(position.y) || 0;
    const cz = Number(position.z) || 0;

    controls.target.set(cx, cy, cz);

    switch (cameraPresetTrigger.preset) {
      case 'x_pos':
        camera.position.set(cx + dist * 1.3, cy, cz);
        break;
      case 'x_neg':
        camera.position.set(cx - dist * 1.3, cy, cz);
        break;
      case 'y_pos':
        camera.position.set(cx, cy + dist * 1.3, cz + 0.001);
        break;
      case 'y_neg':
        camera.position.set(cx, cy - dist * 1.3, cz + 0.001);
        break;
      case 'z_pos':
        camera.position.set(cx, cy, cz + dist * 1.3);
        break;
      case 'z_neg':
        camera.position.set(cx, cy, cz - dist * 1.3);
        break;
      case 'iso':
      default:
        camera.position.set(cx + dist, cy + dist * 0.78, cz + dist);
        break;
    }
    controls.update();
  }, [cameraPresetTrigger, model.geometry.dimensions, model.geometry.position]);

  const activeFaceInfo = getSemanticFacePlaneTransform(
    hoveredFace ?? selectedFace,
    model.geometry.dimensions,
    model.mesh.divisions
  );
  const activeBc = model.boundary_conditions[hoveredFace ?? selectedFace];
  const activeDesc = SEMANTIC_FACE_DESCRIPTORS[hoveredFace ?? selectedFace];
  const lengthUnit = model.units.length;
  const tempUnit = model.units.temperature;

  return (
    <section className="viewport-panel" aria-label="3D Engineering Viewport">
      <div
        ref={containerRef}
        className="viewport-canvas-container"
        data-testid="three-viewport-canvas"
      />

      {/* Top-Left HUD: Active Semantic Face & Quick Face Picker */}
      <div className="viewport-hud viewport-hud-top-left">
        <div className="hud-card">
          <div className="hud-card-header">
            <span className="hud-badge-label">
              {hoveredFace ? 'HOVERING FACE' : 'SELECTED BOUNDARY FACE'}
            </span>
            <span className={`hud-face-tag ${hoveredFace ? 'is-hovered' : 'is-selected'}`}>
              {activeDesc.faceId} ({activeDesc.shortLabel})
            </span>
          </div>
          <div className="hud-telemetry-grid">
            <div>
              <span className="hud-meta-key">Outward Normal:</span>{' '}
              <code>
                ({activeFaceInfo.outwardNormal.x}, {activeFaceInfo.outwardNormal.y},{' '}
                {activeFaceInfo.outwardNormal.z})
              </code>
            </div>
            <div>
              <span className="hud-meta-key">Surface Area:</span>{' '}
              <code>
                {activeFaceInfo.area.toFixed(4)} {lengthUnit}²
              </code>
            </div>
            <div>
              <span className="hud-meta-key">Assigned BC:</span>{' '}
              <strong className={`bc-inline-pill bc-${activeBc.type}`}>
                {activeBc.type.toUpperCase()}
                {activeBc.type === 'dirichlet' && activeBc.temperature !== null
                  ? ` (${activeBc.temperature} ${tempUnit})`
                  : ''}
                {activeBc.type === 'neumann' && activeBc.heat_flux !== null
                  ? ` (${activeBc.heat_flux} W/m²)`
                  : ''}
                {activeBc.type === 'robin' && activeBc.convection_coefficient !== null
                  ? ` (h=${activeBc.convection_coefficient}, T∞=${activeBc.ambient_temperature} ${tempUnit})`
                  : ''}
              </strong>
            </div>
          </div>

          <div className="hud-face-selector-row" role="group" aria-label="Semantic Face Selector">
            {ALL_FACE_IDS.map((fid) => (
              <button
                key={fid}
                type="button"
                data-testid={`viewport-face-btn-${fid}`}
                className={`hud-face-chip ${selectedFace === fid ? 'active' : ''} ${
                  hoveredFace === fid ? 'hovered' : ''
                }`}
                onClick={() => onSelectFace(fid)}
                onMouseEnter={() => onHoverFace(fid)}
                onMouseLeave={() => onHoverFace(null)}
                title={`Select semantic boundary face ${fid}`}
              >
                {fid}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Top-Right HUD: Camera Orientation Presets, Post-Processing Controls & Scalar Legend */}
      <div className="viewport-hud viewport-hud-top-right">
        <div className="hud-toolbar-group" role="group" aria-label="Camera Presets">
          <button
            type="button"
            className="hud-btn"
            onClick={() => onTriggerCameraPreset('iso')}
            title="Reset to Isometric View"
          >
            Reset / ISO
          </button>
          <button
            type="button"
            className="hud-btn"
            onClick={() => onTriggerCameraPreset('x_pos')}
          >
            +X
          </button>
          <button
            type="button"
            className="hud-btn"
            onClick={() => onTriggerCameraPreset('x_neg')}
          >
            -X
          </button>
          <button
            type="button"
            className="hud-btn"
            onClick={() => onTriggerCameraPreset('y_pos')}
          >
            +Y
          </button>
          <button
            type="button"
            className="hud-btn"
            onClick={() => onTriggerCameraPreset('y_neg')}
          >
            -Y
          </button>
          <button
            type="button"
            className="hud-btn"
            onClick={() => onTriggerCameraPreset('z_pos')}
          >
            +Z
          </button>
          <button
            type="button"
            className="hud-btn"
            onClick={() => onTriggerCameraPreset('z_neg')}
          >
            -Z
          </button>
        </div>

        <div className="hud-toolbar-group" role="group" aria-label="Viewport Display Toggles">
          {simulationResult && onToggleContourField && (
            <button
              type="button"
              data-testid="toggle-3d-contour-btn"
              className={`hud-btn ${showContourField ? 'is-on' : ''}`}
              onClick={onToggleContourField}
              title="Toggle between 3D FEM Temperature Contour Field and CAD Boundary View"
            >
              🌡 3D Temp Field
            </button>
          )}
          <button
            type="button"
            className={`hud-btn ${showGrid ? 'is-on' : ''}`}
            onClick={onToggleGrid}
          >
            Grid
          </button>
          <button
            type="button"
            className={`hud-btn ${showAxes ? 'is-on' : ''}`}
            onClick={onToggleAxes}
          >
            Axes
          </button>
          <button
            type="button"
            className={`hud-btn ${showMeshLines ? 'is-on' : ''}`}
            onClick={onToggleMeshLines}
          >
            Mesh Grid
          </button>
          <button
            type="button"
            className={`hud-btn ${showBcColors ? 'is-on' : ''}`}
            onClick={onToggleBcColors}
          >
            BC Colors
          </button>
        </div>

        {/* 3D FEM Temperature Scalar Legend & Cross-Section Slicing Controls */}
        {simulationResult && showContourField && (
          <div className="hud-colorbar-card" data-testid="viewport-temperature-colorbar">
            <div className="colorbar-title">
              <span>Temperature ({simulationResult.temperature_unit})</span>
              <select
                aria-label="Scientific Colormap"
                data-testid="colormap-select"
                value={colormap}
                onChange={(e) => setColormap(e.target.value as ScientificColormap)}
                style={{
                  marginLeft: '0.5rem',
                  background: '#0f172a',
                  color: '#e2e8f0',
                  border: '1px solid #334155',
                  borderRadius: '4px',
                  fontSize: '0.72rem',
                  padding: '1px 4px',
                }}
              >
                <option value="viridis">Viridis</option>
                <option value="inferno">Inferno</option>
                <option value="coolwarm">CoolWarm</option>
                <option value="plasma">Plasma</option>
                <option value="jet">Jet Thermal</option>
              </select>
            </div>
            <div
              className="colorbar-gradient"
              style={{ background: getColormapCssGradient(colormap) }}
            />
            <div className="colorbar-labels">
              <span>Min: {simulationResult.min_temperature_display.toFixed(1)}</span>
              <span>Mean: {simulationResult.mean_temperature_display.toFixed(1)}</span>
              <span>Max: {simulationResult.max_temperature_display.toFixed(1)}</span>
            </div>
            <div className="colorbar-sub">
              {simulationResult.mesh_tetrahedra} Tets • {simulationResult.mesh_vertices} Nodes • P
              {simulationResult.polynomial_order} FEM
            </div>

            {/* 3D Cross-Section Clipping & Slice Controls */}
            <div
              style={{
                marginTop: '0.45rem',
                paddingTop: '0.45rem',
                borderTop: '1px solid rgba(148, 163, 184, 0.2)',
                fontSize: '0.74rem',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '0.25rem',
                }}
              >
                <span style={{ color: '#94a3b8', fontWeight: 600 }}>3D Cross-Section Slice:</span>
                <div style={{ display: 'flex', gap: '3px' }}>
                  {(['none', 'x', 'y', 'z'] as const).map((ax) => (
                    <button
                      key={ax}
                      type="button"
                      data-testid={`clip-axis-btn-${ax}`}
                      className={`hud-btn ${clipAxis === ax ? 'is-on' : ''}`}
                      style={{ padding: '1px 6px', fontSize: '0.7rem' }}
                      onClick={() => setClipAxis(ax)}
                    >
                      {ax === 'none' ? 'Off' : ax.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {clipAxis !== 'none' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <input
                    type="range"
                    aria-label="Slice Position"
                    data-testid="clip-offset-slider"
                    min={-45}
                    max={45}
                    step={5}
                    value={clipOffsetPct}
                    onChange={(e) => setClipOffsetPct(Number(e.target.value))}
                    style={{ flex: 1 }}
                  />
                  <span style={{ minWidth: '34px', textAlign: 'right', color: '#cbd5e1' }}>
                    {clipOffsetPct > 0 ? `+${clipOffsetPct}%` : `${clipOffsetPct}%`}
                  </span>
                  <button
                    type="button"
                    className={`hud-btn ${invertClip ? 'is-on' : ''}`}
                    style={{ padding: '1px 5px', fontSize: '0.68rem' }}
                    onClick={() => setInvertClip((prev) => !prev)}
                    title="Invert Clipping Plane Direction"
                  >
                    Flip
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Bottom-Left HUD: Coordinate Legend & BC Color Legend */}
      <div className="viewport-hud viewport-hud-bottom-left">
        <div className="hud-legend-bar">
          <span className="axis-indicator axis-x">X (Width)</span>
          <span className="axis-indicator axis-y">Y (Height)</span>
          <span className="axis-indicator axis-z">Z (Depth)</span>
          <span className="hud-divider">|</span>
          <span className="bc-dot bc-dirichlet">Dirichlet</span>
          <span className="bc-dot bc-robin">Robin</span>
          <span className="bc-dot bc-neumann">Neumann</span>
          <span className="bc-dot bc-insulated">Insulated</span>
          <span className="hud-divider">|</span>
          <span className="hud-controls-hint">
            Click face in 3D or chips to inspect • LMB: Orbit • RMB: Pan • Scroll: Zoom
          </span>
        </div>
      </div>
    </section>
  );
};
