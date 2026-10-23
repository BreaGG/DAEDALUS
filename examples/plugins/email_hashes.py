"""Example DAEDALUS plugin.

Copy this file into the `plugins/` folder inside your DAEDALUS data directory
(./data/plugins when running from a source checkout) and restart DAEDALUS.
The new transform shows up in the right-click menu of every email entity.
"""

import hashlib

from daedalus.transforms import L, Transform, register


@register
class EmailHashes(Transform):
    name = "plugin_email_hashes"
    title = L("To MD5 / SHA-256 hashes", "A hashes MD5 / SHA-256")
    description = L("Hashes of the normalised address, as used by Gravatar and many leak dumps.",
                    "Hashes de la dirección normalizada, como los usan Gravatar y muchos volcados de filtraciones.")
    category = "utility"
    inputs = ("email",)
    outputs = ("hash",)
    default = False  # do not include it in "run all"

    async def run(self, ctx):
        email = ctx.value.strip().lower().encode()
        ctx.add("hash", hashlib.md5(email).hexdigest(), {"algorithm": "MD5"}, label="MD5")  # noqa: S324
        ctx.add("hash", hashlib.sha256(email).hexdigest(), {"algorithm": "SHA-256"}, label="SHA-256")
