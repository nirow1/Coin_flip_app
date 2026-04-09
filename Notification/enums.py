import enum


class NotificationType(str, enum.Enum):
    flip_result = "flip_result"
    elimination = "elimination"
    showdown_activated = "showdown_activated"
    game_started = "game_started"
    game_won = "game_won"
    prize_paid = "prize_paid"
    side_assigned = "side_assigned"
    friend_invite = "friend_invite"
    new_game_available = "new_game_available"
    credit_purchase_confirmed = "credit_purchase_confirmed"
    wallet_deposit = "wallet_deposit"
    wallet_withdrawal = "wallet_withdrawal"
    general = "general"

