from pathlib import Path
R=Path(__file__).resolve().parent
s=(R/'sigil_02_repair_lightning_branched.py').read_text()
s=s.replace("dest=B/f'discharge-branched-{event:02}.npz'","dest=B/f'discharge-train-{VARIANT}-{event:02}.npz'")
s=s.replace('rng=np.random.default_rng(18301+event*379)','rng=np.random.default_rng(18301+event*379+VARIANT*13007)')
s=s.replace('(stage+event)%2','(stage+event+VARIANT)%2')
s=s.replace('def channel(','''def select_net(f,net):
    # A return stroke reuses its channel for milliseconds; a later discharge
    # grows a fresh tree. This avoids repeatedly blinking one fixed wire logo.
    train=int(np.searchsorted([1.99,2.73,3.32,4.08],f/FPS,side='right'))
    return net['versions'][train] if 'versions' in net else net

def channel(''')
s=s.replace('for event,net in enumerate(nets):\n        energy','for event,net in enumerate(nets):\n        net=select_net(f,net)\n        energy')
s=s.replace('for e,net in enumerate(nets):\n            energy','for e,net in enumerate(nets):\n            net=select_net(f,net)\n            energy')
s=s.replace("started=time.time();nets=[grow(i) for i in range(len(EVENTS))]", "started=time.time();families=[]\n    for VARIANT in range(5):families.append([grow(i) for i in range(len(EVENTS))])\n    nets=[dict(families[0][i],versions=[family[i] for family in families]) for i in range(len(EVENTS))]")
s=s.replace("B/'lightning-pilot-branched.jpg'","B/'lightning-pilot-fresh-channels.jpg'")
(R/'sigil_02_repair_lightning_ensemble.py').write_text(s)
print('Prepared five independently grown discharge trains.')
