'use strict';

const params = new URLSearchParams(location.search);
const variant = params.get('variant') === '02' ? '02' : '01';
document.getElementById('sigil').src = `sigil-${variant}.png`;

void WaterCache.startViewer({ variant, setup(renderer, currentFrame) {
  const backdrop = document.createElement('canvas');
  backdrop.width = backdrop.height = 512;
  const context = backdrop.getContext('2d');
  const gradient = context.createLinearGradient(0, 0, 512, 512);
  gradient.addColorStop(0, '#293c48');
  gradient.addColorStop(0.48, '#82979e');
  gradient.addColorStop(1, '#304654');
  context.fillStyle = gradient;
  context.fillRect(0, 0, 512, 512);
  const map = new THREE.CanvasTexture(backdrop);
  map.colorSpace = THREE.SRGBColorSpace;
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(12, 7), new THREE.MeshBasicMaterial({ map }));
  wall.position.set(2.8, 2, 0.12);
  renderer.scene.add(wall);

  WaterCache.orbitCamera(renderer, function () {
    const u = Math.max(0, Math.min(1, (currentFrame() - 94) / 64));
    const ease = u * u * (3 - 2 * u);
    this.camera.position.set(2.8 + 0.08 * ease, 3.15 + 0.85 * ease, 4.65 + 1.65 * ease);
    this.target.set(2.8, 2.15 - 1.60 * ease, 0.90);
    this.camera.fov = 38;
    this.camera.updateProjectionMatrix();
    const fit = Math.max(1, (16 / 9) / this.camera.aspect);
    this.camera.position.sub(this.target).multiplyScalar(fit).add(this.target);
    this.camera.lookAt(this.target);
  });
} });
