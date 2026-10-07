import test from 'node:test';
import assert from 'node:assert/strict';
import {POWER_DEFINITIONS,powerSourceFor} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-powers.js';
import {powerContactShader} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/power-contacts.js';
for(const definition of POWER_DEFINITIONS)test(definition.id+' contact dependencies survive specialization',()=>{
 const code=powerContactShader(definition.kind);
 assert.match(code,/fn abilityFloorContact\(/);
 assert.match(code,/fn main\(/);
 assert.match(code,/fn powerRecording\(\)->bool\{return true;/);
 // Contact-specific dependencies cannot contaminate the cached fluid source.
 const fluid=powerSourceFor(definition.kind);
 assert.match(fluid,/fn powerRecording\(\)->bool\{return false;/);
});
