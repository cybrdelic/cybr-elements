# Shared movement trail

All four material tests now consume one sampled trajectory: `shared-trail.json`. It preserves the fire test’s sweep and loop. All four videos are 1920 x 1080, four seconds, 120 frames at 30 fps.

- Fire: existing combustion treatment rerendered through the shared trajectory adapter.
- Air: isolated puff replaced by the same moving source and timing.
- Water: opposing jets replaced by one moving FLIP source. Spatial scale 0.4 and simulation-time scale 0.3 map into the same screen-space choreography. The native solver and renderer are retained. A perspective camera matched at the source plane preserves the water shader’s depth assumptions.
- Earth: impact scene replaced by 300 emitted convex stone bodies along the same path. Initial momentum follows the tangent. Authored lift keeps the drawing beat suspended; gravity increases after the source ends, with Bullet handling free motion and contact.

The comparison page plays, pauses, restarts and scrubs all four together. The optional Source path overlay is diagnostic only and is off by default. Previous tests remain available through the archive link.

The movement correction is complete. This does not establish final material quality: water is still dark against black, air remains smoke-like, and stone emission needs further art direction before the complete sigil intros. Material wakes intentionally evolve differently after leaving their common source.
