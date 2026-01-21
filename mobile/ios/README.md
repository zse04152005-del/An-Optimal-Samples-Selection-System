# iOS Build Notes (Kivy)

This repo includes a Kivy-based mobile UI under `mobile/`.

iOS packaging typically requires:

- macOS + Xcode
- A valid Apple Developer signing setup
- `kivy-ios` toolchain

High-level steps (outline):

1. Install `kivy-ios` and initialize the toolchain.
2. Build the Python/Kivy toolchain and required recipes.
3. Create an Xcode project for this app.
4. Open the project in Xcode, configure signing, then build/run.

Because iOS toolchains evolve frequently, the exact commands depend on your
installed versions of Xcode / iOS SDK / kivy-ios.
