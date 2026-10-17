# Front-panel clock repair 1.0.1

The reviewed receiver had an existing `GTFrontPanel/plugin.py` whose module
docstring described channel numbers/standby clock although its implementation
already displayed a permanent local clock. The published 1.0.0 payload differed
only in that docstring. Its hash was absent from the repair's reviewed `before`
inventory, so the engine correctly rejected the install.

Version 1.0.1 explicitly accepts that reviewed SHA256
`4e9ee5624eb10a76e6ed50d27d51447bd379e5b59e19b81ee4d7ab9f27accf13`.
The executable payload, GPIO driver, worker and safety checks are unchanged.
Unknown local variants are still rejected. The archive's package version and
catalog metadata are both 1.0.1, with new archive size/digest. Local timezone and
system clock synchronization are separate from this front display repair.
