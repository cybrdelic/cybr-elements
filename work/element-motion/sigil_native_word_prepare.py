from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;B=R/'sigil-native';s=(R/'sigil_native_fire_fed2.py').read_text(encoding='utf-8')
s=s.replace('from sigil_native_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE','from sigil_word_motion import pose as nozzle_pose, turn_rate as nozzle_turn, WRITE, START, MODE, VARIANT')
s=s.replace("ROOT/'sigil-native/fire-c-fed2'","ROOT/f'sigil-native/fire-{VARIANT}'").replace("ROOT/'sigil-native/fire-c-fed2.mp4'","ROOT/f'sigil-native/fire-{VARIANT}.mp4'").replace("ROOT/'sigil-native/fire-c-fed2-report.json'","ROOT/f'sigil-native/fire-{VARIANT}-report.json'")
s=s.replace('TOTAL=120 if a.pilot else round(DURATION*FPS)','TOTAL=330')
s=s.replace('if t>=2.4:reservoir','if t>=8.2:reservoir')
s=s.replace('    render(frame)\nencoder.stdin.close()',"    render(frame)\n    if frame==180:\n        print('REVIEW GATE native fire '+VARIANT,flush=True)\n        while not (ROOT/f'sigil-native/continue-fire-{VARIANT}').exists():time.sleep(.5)\nencoder.stdin.close()")
s=s.replace('Single moving fuel nozzle with backward jet momentum; speed-preserving hot-gas turning; native buoyancy, reaction, pressure and radiance; no trail fitting, morph or cached particles.','Accepted bending-fire solver/radiance with the approved sigil centerline as motion input. A moving nozzle deposits a narrow gas source and tangential source momentum, supplied until 8.2s then drained. No silhouette clipping or filled glyph volume. Art-directed source, free reacting wake.')
(R/'sigil_native_word_fire.py').write_text(s,encoding='utf-8')
original=(R/'bending-fire.py').read_text(encoding='utf-8')
for name,end in [('radiance','capture')]:
 a=original[original.index('def '+name+'('):original.index('def '+end+'(')];b=s[s.index('def '+name+'('):s.index('def '+end+'(')];assert a==b
print('Prepared full-word source-only adapter. Original radiance unchanged. Review gate at 6 seconds.')
