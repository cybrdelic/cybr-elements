import {shaderFunctionsToGLSL} from './shader-language.js?v=studio-rc-37-repair';
// Both renderers display the same HDR units. Keep exposure, highlight hue
// and the sRGB transfer in one place; the volume port used 1.92x exposure.
export const firePresentationWGSL=`
fn fireToneCurve(x:vec3f)->vec3f{return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),vec3f(0),vec3f(1));}
fn presentFire(hdr:vec3f)->vec3f{
 let linear:vec3f=max(hdr,vec3f(0))*.60;
 let luminance:f32=dot(linear,vec3f(.2126,.7152,.0722));
 let hue:vec3f=linear*fireToneCurve(vec3f(luminance)).x/max(luminance,.00001);
 let mapped:vec3f=mix(fireToneCurve(linear),clamp(hue,vec3f(0),vec3f(1)),.45);
 return mix(mapped*12.92,1.055*pow(mapped,vec3f(1./2.4))-.055,step(vec3f(.0031308),mapped));
}
`;
export const firePresentationGLSL=shaderFunctionsToGLSL(firePresentationWGSL);
