import { describe, expect, it } from 'vitest';
import { ALL_FACE_IDS } from '../types/model';
import {
  getSemanticFacePlaneTransform,
  resolveSemanticFaceFromHit,
  resolveSemanticFaceFromLocalNormal,
  SEMANTIC_FACE_DESCRIPTORS,
} from '../utils/semanticFaces';

describe('Semantic Cuboid Face Identification (No Triangle Indices)', () => {
  it('defines all 6 canonical semantic face IDs with unit outward normals', () => {
    expect(ALL_FACE_IDS).toEqual(['X_MIN', 'X_MAX', 'Y_MIN', 'Y_MAX', 'Z_MIN', 'Z_MAX']);
    for (const fid of ALL_FACE_IDS) {
      const n = SEMANTIC_FACE_DESCRIPTORS[fid].outwardNormal;
      const len = Math.hypot(n.x, n.y, n.z);
      expect(len).toBeCloseTo(1.0, 6);
    }
  });

  it('resolves semantic faces deterministically from local normal vectors', () => {
    expect(resolveSemanticFaceFromLocalNormal({ x: -0.98, y: 0.02, z: 0.01 })).toBe('X_MIN');
    expect(resolveSemanticFaceFromLocalNormal({ x: 0.95, y: -0.05, z: 0.0 })).toBe('X_MAX');
    expect(resolveSemanticFaceFromLocalNormal({ x: 0.01, y: -0.99, z: 0.02 })).toBe('Y_MIN');
    expect(resolveSemanticFaceFromLocalNormal({ x: -0.01, y: 0.99, z: 0.0 })).toBe('Y_MAX');
    expect(resolveSemanticFaceFromLocalNormal({ x: 0.0, y: 0.02, z: -0.99 })).toBe('Z_MIN');
    expect(resolveSemanticFaceFromLocalNormal({ x: 0.0, y: -0.02, z: 0.99 })).toBe('Z_MAX');
  });

  it('prioritizes explicit mesh userData.faceId and falls back to local normal', () => {
    expect(resolveSemanticFaceFromHit({ faceId: 'Y_MAX' })).toBe('Y_MAX');
    expect(resolveSemanticFaceFromHit({}, { x: -1, y: 0, z: 0 })).toBe('X_MIN');
    expect(resolveSemanticFaceFromHit(undefined)).toBeNull();
  });

  it('computes accurate face areas and centers for a parametric rectangular cuboid', () => {
    const dims = { length_x: 2.0, length_y: 3.0, length_z: 4.0 };
    const xMin = getSemanticFacePlaneTransform('X_MIN', dims);
    expect(xMin.center).toEqual({ x: -1.0, y: 0, z: 0 });
    expect(xMin.area).toBeCloseTo(12.0, 6);

    const zMax = getSemanticFacePlaneTransform('Z_MAX', dims);
    expect(zMax.center).toEqual({ x: 0, y: 0, z: 2.0 });
    expect(zMax.area).toBeCloseTo(6.0, 6);
  });
});
