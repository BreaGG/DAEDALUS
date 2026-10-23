"""Blockchain transforms: wallet balances, activity and counterparties."""

from __future__ import annotations

from datetime import datetime, timezone

from ..entities import CRYPTO_NAMES, L, crypto_chain
from .base import Skip, Transform, register

BLOCKSTREAM = "https://blockstream.info/api"
BLOCKSCOUT = "https://eth.blockscout.com/api/v2"


def _day(ts) -> str | None:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


class _ChainTransform(Transform):
    chains: tuple[str, ...] = ()

    def applies(self, entity: dict) -> bool:
        return entity["type"] == "crypto" and crypto_chain(entity["value"]) in self.chains


@register
class WalletInfo(_ChainTransform):
    name = "wallet_info"
    title = L("To balance and activity", "A saldo y actividad")
    description = L("Balance, transaction count and first/last activity (Bitcoin via Blockstream, Ethereum via "
                    "Blockscout).",
                    "Saldo, número de transacciones y primera/última actividad (Bitcoin con Blockstream, Ethereum "
                    "con Blockscout).")
    category = "crypto"
    inputs = ("crypto",)
    chains = ("btc", "eth")
    sources = ("Blockstream", "Blockscout")

    async def run(self, ctx):
        chain = crypto_chain(ctx.value)
        if chain == "btc":
            await self._btc(ctx)
        else:
            await self._eth(ctx)

    async def _btc(self, ctx):
        st, d = await ctx.get_json(f"{BLOCKSTREAM}/address/{ctx.value}")
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"Blockstream HTTP {st}")
        cs = d.get("chain_stats") or {}
        sats = (cs.get("funded_txo_sum") or 0) - (cs.get("spent_txo_sum") or 0)
        props = {"chain": CRYPTO_NAMES["btc"], "balance": f"{sats / 1e8:.8f} BTC", "tx_count": cs.get("tx_count"),
                 "total_received": f"{(cs.get('funded_txo_sum') or 0) / 1e8:.8f} BTC",
                 "_links": [["Blockstream", f"https://blockstream.info/address/{ctx.value}"],
                            ["Mempool", f"https://mempool.space/address/{ctx.value}"]]}
        st, txs = await ctx.get_json(f"{BLOCKSTREAM}/address/{ctx.value}/txs")
        if st == 200 and isinstance(txs, list) and txs:
            times = [t["status"]["block_time"] for t in txs if (t.get("status") or {}).get("block_time")]
            if times:
                props["last_activity"] = _day(max(times))
                props["_dates"] = [["Last wallet activity", _day(max(times))]]
        ctx.enrich(props)

    async def _eth(self, ctx):
        st, d = await ctx.get_json(f"{BLOCKSCOUT}/addresses/{ctx.value}")
        if st == 404:
            ctx.enrich({"chain": CRYPTO_NAMES["eth"], "balance": "0 ETH (never used)"})
            return
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"Blockscout HTTP {st}")
        wei = int(d.get("coin_balance") or 0)
        props = {"chain": CRYPTO_NAMES["eth"], "balance": f"{wei / 1e18:.6f} ETH", "is_contract": d.get("is_contract"),
                 "ens_name": d.get("ens_domain_name"), "label": d.get("name"),
                 "_links": [["Etherscan", f"https://etherscan.io/address/{ctx.value}"],
                            ["Blockscout", f"https://eth.blockscout.com/address/{ctx.value}"]]}
        st, c = await ctx.get_json(f"{BLOCKSCOUT}/addresses/{ctx.value}/counters")
        if st == 200 and isinstance(c, dict):
            props["tx_count"] = c.get("transactions_count")
            props["token_transfers"] = c.get("token_transfers_count")
        ctx.enrich(props)


@register
class WalletCounterparties(_ChainTransform):
    name = "wallet_counterparties"
    title = L("To counterparty wallets", "A carteras contraparte")
    description = L("Addresses that sent to or received from this wallet in its most recent transactions.",
                    "Direcciones que enviaron o recibieron fondos de esta cartera en sus últimas transacciones.")
    category = "crypto"
    inputs = ("crypto",)
    outputs = ("crypto",)
    chains = ("btc", "eth")
    sources = ("Blockstream", "Blockscout")
    default = False

    async def run(self, ctx):
        me = ctx.value
        if crypto_chain(me) == "btc":
            st, txs = await ctx.get_json(f"{BLOCKSTREAM}/address/{me}/txs")
            if st != 200 or not isinstance(txs, list):
                raise Skip(f"Blockstream HTTP {st}")
            for tx in txs:
                ins = {(v.get("prevout") or {}).get("scriptpubkey_address") for v in tx.get("vin") or []}
                outs = {v.get("scriptpubkey_address") for v in tx.get("vout") or []}
                sent = me in ins
                others = (outs if sent else ins) - {me, None}
                for addr in others:
                    if ctx.add("crypto", addr, {"chain": "Bitcoin"}, label="sent to",
                               reverse=not sent) is None:
                        return
            return
        st, d = await ctx.get_json(f"{BLOCKSCOUT}/addresses/{me}/transactions")
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"Blockscout HTTP {st}")
        for tx in d.get("items") or []:
            src = ((tx.get("from") or {}).get("hash") or "")
            dst = ((tx.get("to") or {}).get("hash") or "")
            sent = src.lower() == me.lower()
            other = dst if sent else src
            if other and other.lower() != me.lower():
                if ctx.add("crypto", other, {"chain": "Ethereum / EVM"}, label="sent to",
                           reverse=not sent) is None:
                    return
