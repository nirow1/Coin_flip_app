from pathlib import Path

p = Path(r"c:\Users\gunmo\Desktop\Github_projects\test_projects\Coin_flip_app\Backend\Game\service.py")
text = p.read_text(encoding="utf-8")

replacements = [
    (
        "invite",
        '''        await wallet.debit(user_id, Decimal("1.00"))
        await self._add_player_to_game(game, friend_id, None)
        return True''',
        '''        await wallet.debit(user_id, Decimal("1.00"))
        # TODO(void-game): store paid_by_user_id=user_id on the GamePlayer so cancel/void
        # refunds the inviter, not friend_id.
        await self._add_player_to_game(game, friend_id, None)
        return True''',
    ),
    (
        "cashouts",
        '''        # 2. Process cashouts
        payout = (game.prize_pool / len(players)).quantize(Decimal("0.01"))''',
        '''        # 2. Process cashouts
        # TODO(void-game): once any cashout runs, cancel cannot be a simple seat refund —
        # need clawback of credited amounts + lockdown if funds were withdrawn.
        payout = (game.prize_pool / len(players)).quantize(Decimal("0.01"))''',
    ),
    (
        "cancel",
        '''    async def cancel_stale_open_games(self):
        games = await self.get_open_games()
        for game in games:
            if game.flip_time < datetime.now(timezone.utc) - timedelta(minutes=5):
                await self.cancel_game(game.id)

    async def cancel_game(self, game_id: int, wallet: WalletService):
        game = await self._get_game_by_id(game_id)
        async for player in self._get_players_for_game(game_id):
            await self._refund(player, game, wallet)

        game.status = "canceled"
        await self.session.flush()
        return game''',
        '''    async def cancel_stale_open_games(self, wallet: WalletService):
        games = await self.get_open_games()
        for game in games:
            if game.flip_time < datetime.now(timezone.utc) - timedelta(minutes=5):
                await self.cancel_game(game.id, wallet)

    async def cancel_game(self, game_id: int, wallet: WalletService):
        """Cancel an open/active game and refund each seat's join fee.

        TODO(void-game): showdown_pending / showdown_active / finished need a separate
        admin void path — cashouts may already have left the pool, leaderboard earnings
        and streaks must be reversed, and withdrawn winnings need a funds-lockdown /
        clawback policy. Do not extend this seat-refund path to those states.
        """
        game = await self._get_game_by_id(game_id)

        if game.status not in ("open", "active"):
            raise ValueError(
                f"Cannot cancel game in status '{game.status}'; "
                "only open/active supported (see TODO void-game)"
            )

        # All seats who paid — including eliminated in active games
        players = await self.get_all_players(game_id)
        for player in players:
            await self._refund(player, game, wallet)

        game.prize_pool = Decimal("0")
        game.status = "canceled"
        await self.session.flush()
        return game''',
    ),
    (
        "refund",
        '''    async def _refund(self, player: GamePlayer, game: Game, wallet: WalletService):
        await wallet.credit(player.user_id, Decimal("1.00"))
        await self.session.flush()
        return True

    async def _cashout(self, player: GamePlayer,
                       game: Game, payout: Decimal,
                       wallet: WalletService,
                       leaderboard: LeaderBoardService) -> Decimal:
        if player.is_eliminated:
            raise ValueError("Eliminated players cannot cash out")

        if game.status not in ("showdown_pending", "finished"):
            raise ValueError("Cannot cash out in this game state")

        player.is_eliminated = True
        player.eliminated_at = datetime.now(timezone.utc)

        await wallet.credit(player.user_id, payout)
        await leaderboard.increment_earnings(player.user_id, payout)
        await leaderboard.update_streak(player.user_id, player.round_number)
        await self.session.flush()
        return payout''',
        '''    async def _refund(self, player: GamePlayer, game: Game, wallet: WalletService):
        # TODO(void-game): credit with TransactionType.REFUND; refund paid_by_user_id
        # when invite_friend paid for this seat (today credits GamePlayer.user_id).
        # TODO(void-game): for finished/showdown void, seat refund is wrong — claw back
        # recorded payouts instead (and skip seats that already received a WIN credit).
        await wallet.credit(player.user_id, Decimal("1.00"))
        await self.session.flush()
        return True

    async def _cashout(self, player: GamePlayer,
                       game: Game, payout: Decimal,
                       wallet: WalletService,
                       leaderboard: LeaderBoardService) -> Decimal:
        if player.is_eliminated:
            raise ValueError("Eliminated players cannot cash out")

        if game.status not in ("showdown_pending", "finished"):
            raise ValueError("Cannot cash out in this game state")

        player.is_eliminated = True
        player.eliminated_at = datetime.now(timezone.utc)

        # TODO(void-game): persist payout on GamePlayer (e.g. amount_won) so a later
        # void can claw back the exact credited amount and reverse leaderboard rows.
        await wallet.credit(player.user_id, payout)
        await leaderboard.increment_earnings(player.user_id, payout)
        await leaderboard.update_streak(player.user_id, player.round_number)
        await self.session.flush()
        return payout''',
    ),
    (
        "state",
        '''    async def _set_game_state(self, game: Game, state: str) -> Game:
        """Utility to set game state with validation."""
        if state not in ("open", "active", "showdown_pending", "showdown_active", "finished"):
            raise ValueError("Invalid game state")''',
        '''    async def _set_game_state(self, game: Game, state: str) -> Game:
        """Utility to set game state with validation."""
        # TODO(void-game): add "canceled" once cancel_game goes through this helper
        if state not in ("open", "active", "showdown_pending", "showdown_active", "finished"):
            raise ValueError("Invalid game state")''',
    ),
]

for name, old, new in replacements:
    if old not in text:
        print(f"MISSING: {name}")
    else:
        text = text.replace(old, new, 1)
        print(f"OK: {name}")

p.write_text(text, encoding="utf-8")
print("done")
