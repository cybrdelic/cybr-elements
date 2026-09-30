'use strict';

const params = new URLSearchParams(location.search);
const variants = ['01', '02', '03', 'shared', 'material', 'viscous'];
const variant = variants.includes(params.get('variant')) ? params.get('variant') : '01';
// These two historical studies retained review snapshots, not full sequences.
const snapshots = { '01': [8, 20, 32, 44, 60, 80, 95], '03': [8, 20, 32, 44, 60, 80] };
document.getElementById('variant').value = variant;
document.getElementById('variant').onchange = event => {
  const url = new URL(location.href);
  url.searchParams.set('variant', event.target.value);
  url.searchParams.delete('frame');
  location.assign(url.href);
};

void WaterCache.startViewer({ variant, availableFrames: snapshots[variant], setup(renderer) {
  let authoredCamera = function () {
    this.camera.position.set(3.3, 2.4, 4.3);
    this.target.set(1.95, 0.72, 0.9);
    this.camera.fov = 36;
    this.camera.updateProjectionMatrix();
    const fit = Math.max(1, (16 / 9) / this.camera.aspect);
    this.camera.position.sub(this.target).multiplyScalar(fit).add(this.target);
    this.camera.lookAt(this.target);
  };
  if (variant === 'shared' || variant === 'material' || variant === 'viscous') {
    renderer.objects.visible = false;
    renderer.backgroundFloor.visible = false;
    renderer.scene.background = new THREE.Color(0x050708);
    renderer.scene.fog = null;
    renderer.camera = new THREE.PerspectiveCamera(2 * Math.atan(1.18125 / 5.1) * 180 / Math.PI,
      renderer.width / renderer.height, 0.05, 100);
    renderer.material.uniforms.uNear.value = 0.05;
    renderer.material.uniforms.uFar.value = 100;
    authoredCamera = function () {
      this.target.set(2.1, 0.76125, 0.9);
      this.camera.position.set(2.1, 0.76125, 6);
      const fit = Math.max(1, (16 / 9) / this.camera.aspect);
      this.camera.position.sub(this.target).multiplyScalar(fit).add(this.target);
      this.camera.lookAt(this.target);
      this.camera.updateProjectionMatrix();
    };
  }
  if (variant === 'material') {
    renderer.material.uniforms.uAbsorption.value.set(0.32, 0.065, 0.018);
    renderer.material.fragmentShader = renderer.material.fragmentShader
      .replace('vec2(.80,.20),.045', 'vec2(1.30,.55),.18')
      .replace('vec2(.17,1.15),.05', 'vec2(.42,1.50),.18')
      .replace('vec2(1.4,.16),.055', 'vec2(1.8,.38),.16');
    renderer.material.needsUpdate = true;
  }
  WaterCache.orbitCamera(renderer, authoredCamera);
} });
