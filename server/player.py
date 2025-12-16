# server/player.py
from game_engine import Card

class Player:
    def __init__(self, name, sid=None):
        self.name = name
        self.sid = sid  # ID de socket (pour l'étape 3)
        self.hand = []  # Liste d'objets Card
        self.has_finished = False
        self.finish_rank = None

    def add_cards(self, cards):
        """Ajoute des cartes et trie la main automatiquement"""
        self.hand.extend(cards)
        self.hand.sort()

    def remove_cards(self, cards_to_remove):
        """Retire les cartes jouées de la main"""
        # On utilise les strings ou les valeurs pour identifier les cartes à retirer
        # Pour simplifier, on suppose que cards_to_remove sont des objets Card valides
        for card in cards_to_remove:
            # On cherche une carte correspondante dans la main (valeur et couleur)
            for i, hand_card in enumerate(self.hand):
                if hand_card.rank == card.rank and hand_card.suit == card.suit:
                    self.hand.pop(i)
                    break

    def __repr__(self):
        return f"{self.name} ({len(self.hand)} cartes)"