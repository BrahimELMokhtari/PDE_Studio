/**
 * Semantic Face Identification & Geometry Utilities
 *
 * Guarantees stable semantic boundary identification (X_MIN, X_MAX, Y_MIN, Y_MAX, Z_MIN, Z_MAX)
 * without ever relying on unstable triangle/face indices from Three.js BufferGeometry.
 */

import { ALL_FACE_IDS, CuboidDimensions, FaceId, Vector3D } from '../types/model';

export interface SemanticFaceDescriptor {
  faceId: FaceId;
  shortLabel: string;
  fullLabel: string;
  axis: 'x' | 'y' | 'z';
  sign: -1 | 1;
  outwardNormal: Vector3D;
  eulerRotationRad: Vector3D;
}

export const SEMANTIC_FACE_DESCRIPTORS: Record<FaceId, SemanticFaceDescriptor> = {
  X_MIN: {
    faceId: 'X_MIN',
    shortLabel: '-X (West)',
    fullLabel: 'X_MIN — Negative X Face (-X)',
    axis: 'x',
    sign: -1,
    outwardNormal: { x: -1, y: 0, z: 0 },
    eulerRotationRad: { x: 0, y: -Math.PI / 2, z: 0 },
  },
  X_MAX: {
    faceId: 'X_MAX',
    shortLabel: '+X (East)',
    fullLabel: 'X_MAX — Positive X Face (+X)',
    axis: 'x',
    sign: 1,
    outwardNormal: { x: 1, y: 0, z: 0 },
    eulerRotationRad: { x: 0, y: Math.PI / 2, z: 0 },
  },
  Y_MIN: {
    faceId: 'Y_MIN',
    shortLabel: '-Y (Bottom)',
    fullLabel: 'Y_MIN — Negative Y Face (-Y)',
    axis: 'y',
    sign: -1,
    outwardNormal: { x: 0, y: -1, z: 0 },
    eulerRotationRad: { x: Math.PI / 2, y: 0, z: 0 },
  },
  Y_MAX: {
    faceId: 'Y_MAX',
    shortLabel: '+Y (Top)',
    fullLabel: 'Y_MAX — Positive Y Face (+Y)',
    axis: 'y',
    sign: 1,
    outwardNormal: { x: 0, y: -Math.PI / 2, z: 0 },
    eulerRotationRad: { x: -Math.PI / 2, y: 0, z: 0 },
  },
  Z_MIN: {
    faceId: 'Z_MIN',
    shortLabel: '-Z (Back)',
    fullLabel: 'Z_MIN — Negative Z Face (-Z)',
    axis: 'z',
    sign: -1,
    outwardNormal: { x: 0, y: 0, z: -1 },
    eulerRotationRad: { x: 0, y: Math.PI, z: 0 },
  },
  Z_MAX: {
    faceId: 'Z_MAX',
    shortLabel: '+Z (Front)',
    fullLabel: 'Z_MAX — Positive Z Face (+Z)',
    axis: 'z',
    sign: 1,
    outwardNormal: { x: 0, y: 0, z: 1 },
    eulerRotationRad: { x: 0, y: 0, z: 0 },
  },
};

// Fix Y_MAX outwardNormal typo above to { x: 0, y: 1, z: 0 }
SEMANTIC_FACE_DESCRIPTORS.Y_MAX.outwardNormal = { x: 0, y: 1, z: 0 };

export interface FacePlaneTransform {
  faceId: FaceId;
  center: Vector3D;
  planeWidth: number;
  planeHeight: number;
  gridDivisionsU: number;
  gridDivisionsV: number;
  eulerRotationRad: Vector3D;
  outwardNormal: Vector3D;
  area: number;
}

/**
 * Computes the exact local plane geometry and transform for a semantic cuboid face.
 */
export function getSemanticFacePlaneTransform(
  faceId: FaceId,
  dimensions: CuboidDimensions,
  divisions: { nx: number; ny: number; nz: number } = { nx: 10, ny: 10, nz: 10 }
): FacePlaneTransform {
  const { length_x, length_y, length_z } = dimensions;
  const { nx, ny, nz } = divisions;
  const desc = SEMANTIC_FACE_DESCRIPTORS[faceId];

  switch (faceId) {
    case 'X_MIN':
      return {
        faceId,
        center: { x: -length_x / 2, y: 0, z: 0 },
        planeWidth: length_z,
        planeHeight: length_y,
        gridDivisionsU: nz,
        gridDivisionsV: ny,
        eulerRotationRad: desc.eulerRotationRad,
        outwardNormal: { x: -1, y: 0, z: 0 },
        area: length_y * length_z,
      };
    case 'X_MAX':
      return {
        faceId,
        center: { x: length_x / 2, y: 0, z: 0 },
        planeWidth: length_z,
        planeHeight: length_y,
        gridDivisionsU: nz,
        gridDivisionsV: ny,
        eulerRotationRad: desc.eulerRotationRad,
        outwardNormal: { x: 1, y: 0, z: 0 },
        area: length_y * length_z,
      };
    case 'Y_MIN':
      return {
        faceId,
        center: { x: 0, y: -length_y / 2, z: 0 },
        planeWidth: length_x,
        planeHeight: length_z,
        gridDivisionsU: nx,
        gridDivisionsV: nz,
        eulerRotationRad: desc.eulerRotationRad,
        outwardNormal: { x: 0, y: -1, z: 0 },
        area: length_x * length_z,
      };
    case 'Y_MAX':
      return {
        faceId,
        center: { x: 0, y: length_y / 2, z: 0 },
        planeWidth: length_x,
        planeHeight: length_z,
        gridDivisionsU: nx,
        gridDivisionsV: nz,
        eulerRotationRad: desc.eulerRotationRad,
        outwardNormal: { x: 0, y: 1, z: 0 },
        area: length_x * length_z,
      };
    case 'Z_MIN':
      return {
        faceId,
        center: { x: 0, y: 0, z: -length_z / 2 },
        planeWidth: length_x,
        planeHeight: length_y,
        gridDivisionsU: nx,
        gridDivisionsV: ny,
        eulerRotationRad: desc.eulerRotationRad,
        outwardNormal: { x: 0, y: 0, z: -1 },
        area: length_x * length_y,
      };
    case 'Z_MAX':
      return {
        faceId,
        center: { x: 0, y: 0, z: length_z / 2 },
        planeWidth: length_x,
        planeHeight: length_y,
        gridDivisionsU: nx,
        gridDivisionsV: ny,
        eulerRotationRad: desc.eulerRotationRad,
        outwardNormal: { x: 0, y: 0, z: 1 },
        area: length_x * length_y,
      };
  }
}

/**
 * Resolves a semantic FaceId purely from a local-space outward normal vector
 * by maximizing the dot product against canonical axis normals.
 * Never uses triangle indices.
 */
export function resolveSemanticFaceFromLocalNormal(normal: Vector3D): FaceId {
  const mag = Math.hypot(normal.x, normal.y, normal.z);
  if (mag === 0) {
    throw new Error('Cannot resolve semantic face from zero-length normal vector.');
  }
  const nx = normal.x / mag;
  const ny = normal.y / mag;
  const nz = normal.z / mag;

  let bestFace: FaceId = 'X_MAX';
  let bestDot = -Infinity;

  for (const faceId of ALL_FACE_IDS) {
    const ref = SEMANTIC_FACE_DESCRIPTORS[faceId].outwardNormal;
    const dot = nx * ref.x + ny * ref.y + nz * ref.z;
    if (dot > bestDot) {
      bestDot = dot;
      bestFace = faceId;
    }
  }
  return bestFace;
}

/**
 * Resolves a semantic FaceId from a raycast hit object's userData or local point/normal.
 * Never inspects triangle faceIndex.
 */
export function resolveSemanticFaceFromHit(
  userData: Record<string, unknown> | undefined,
  localNormal?: Vector3D
): FaceId | null {
  if (userData && typeof userData.faceId === 'string') {
    const candidate = userData.faceId as FaceId;
    if ((ALL_FACE_IDS as readonly string[]).includes(candidate)) {
      return candidate;
    }
  }
  if (localNormal) {
    return resolveSemanticFaceFromLocalNormal(localNormal);
  }
  return null;
}
