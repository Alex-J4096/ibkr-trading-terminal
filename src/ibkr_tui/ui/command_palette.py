from __future__ import annotations

from textual.command import Provider, Hits, Hit


class TerminalCommandProvider(Provider):
    async def search(self, query: str) -> Hits:
        commands = [
            ("refresh", "Refresh data now"),
            ("view_selection", "View selected position, quote, or order details"),
            ("buy", "Open buy order ticket for selected symbol"),
            ("sell", "Open sell order ticket for selected symbol"),
            ("flatten", "Flatten selected position"),
            ("flatten_all", "Flatten all positions with strong confirmation"),
            ("cancel_order", "Cancel selected open order"),
            ("cancel_all_orders", "Cancel all open orders with strong confirmation"),
            ("quit", "Quit application"),
        ]
        for name, help_text in commands:
            if query.lower() in name:
                yield Hit(0, name, help_text, lambda command=name: self.app.run_action(command))
