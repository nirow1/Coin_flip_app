import enum


class NotificationType(str, enum.Enum):
    flip_result = "flip_result"
    elimination = "elimination"
    showdown = "showdown"
    game_started = "game_started"
    game_end = "game_end"
    prize_paid = "prize_paid"
    side_assigned = "side_assigned"
    friend_invite = "friend_invite"
    new_game = "new_game"
    credit_purchase = "credit_purchase"
    wallet_deposit = "wallet_deposit"
    wallet_withdrawal = "wallet_withdrawal"
    general = "general"

