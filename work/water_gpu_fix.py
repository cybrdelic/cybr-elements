from pathlib import Path
p=Path('work/render_water_sans.py').read_text().replace("s.cycles.use_adaptive_sampling=True", "s.cycles.use_adaptive_sampling=False")
p=p.replace("s.cycles.device='GPU'", "s.cycles.device='GPU';s.cycles.denoiser='OPTIX';s.cycles.denoising_use_gpu=True;s.render.threads_mode='FIXED';s.render.threads=6")
p=p.replace("dev.use=dev.type!='CPU'", "dev.use=dev.type=='OPTIX'")
p=p.replace("frames=[60,240,345] if pilot else range(450)", "frames=[240] if '--test' in sys.argv else ([60,240,345] if pilot else range(450))")
Path('work/render_water_sans.py').write_text(p)
