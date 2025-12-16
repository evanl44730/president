import random

# Définition des constantes pour faciliter la lecture
SUITS = ['H', 'D', 'C', 'S']  # Hearts, Diamonds, Clubs, Spades
# Ordre visuel classique (pour l'affichage), mais la force sera recalculée
RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']

class Card:
    def __init__(self, rank, suit):
        """
        :param rank: String (ex: '3', '10', 'K', '2')
        :param suit: String (ex: 'H', 'D')
        """
        if rank not in RANKS:
            raise ValueError(f"Rang invalide: {rank}")
        if suit not in SUITS:
            raise ValueError(f"Couleur invalide: {suit}")
        
        self.rank = rank
        self.suit = suit

    @property
    def value(self):
        """
        Retourne la force de la carte selon les règles du Président.
        3 est le plus faible (index 0), 2 est le plus fort (index 12).
        """
        return RANKS.index(self.rank)

    def __repr__(self):
        """Représentation pour le debug et l'envoi JSON (ex: '3H', '10D')"""
        return f"{self.rank}{self.suit}"

    def __eq__(self, other):
        """Vérifie l'égalité de valeur (utile pour les paires/carrés)"""
        if not isinstance(other, Card):
            return False
        return self.value == other.value

    def __lt__(self, other):
        """Permet de trier les cartes et vérifier si une carte est plus faible"""
        if not isinstance(other, Card):
            return NotImplemented
        return self.value < other.value

    def __gt__(self, other):
        """Permet de vérifier si une carte bat une autre"""
        if not isinstance(other, Card):
            return NotImplemented
        return self.value > other.value

class Deck:
    def __init__(self):
        self.cards = []
        self._build()

    def _build(self):
        """Génère les 52 cartes"""
        self.cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]

    def shuffle(self):
        """Mélange le paquet"""
        random.shuffle(self.cards)

    def deal(self, num_hands):
        """
        Distribue toutes les cartes entre le nombre de joueurs spécifié.
        Retourne une liste de listes de cartes (mains).
        """
        hands = [[] for _ in range(num_hands)]
        current_hand = 0
        
        while self.cards:
            card = self.cards.pop()
            hands[current_hand].append(card)
            current_hand = (current_hand + 1) % num_hands
            
        return hands
# ... (Garder les classes Card et Deck de l'étape 1) ...
# N'oublie pas d'importer Player si tu sépares les fichiers, sinon colle tout dans le même fichier pour le test.

class Game:
    def __init__(self):
        self.players = []
        self.deck = Deck()
        self.current_trick = []    # Les dernières cartes posées (ex: [Roi, Roi])
        self.trick_owner = None    # Celui qui a posé le dernier paquet
        self.current_player_index = 0
        self.winners = []         # Liste ordonnée des joueurs ayant fini
        
        self.rank_counter = 0

    def add_player(self, player):
        self.players.append(player)

    def start_game(self):
        """Lance la partie, mélange et distribue"""
        self.deck.shuffle()
        hands = self.deck.deal(len(self.players))
        self.winners = []
        self.current_trick = []
        self.trick_owner = None
        self.rank_counter = 0 # Reset du compteur
        
        for i, player in enumerate(self.players):
            player.hand = []
            player.has_finished = False
            player.add_cards(hands[i])
        
        # Pour le MVP, le joueur 0 commence toujours (ou celui avec 3 de coeur en V2)
        self.current_player_index = 0

    def play_move(self, player_index, cards):
        """
        Gère le coup avec règles flexibles pour finir le Carré (1+3, 2+2, 1+1+2).
        """
        # 1. Gestion du PASSE
        if not cards:
            if player_index != self.current_player_index:
                return False, "Vous ne pouvez pas passer hors de votre tour."
            return self._pass_turn()

        # 2. Vérification homogénéité
        first_rank = cards[0].rank
        if not all(c.rank == first_rank for c in cards):
             return False, "Les cartes jouées doivent être de même rang."

        played_count = len(cards)
        current_trick_count = len(self.current_trick) if self.current_trick else 0
        
        # --- LOGIQUE D'INTERCEPTION (Jeu hors tour) ---
        is_interception = False
        
        if self.current_trick and cards[0].value == self.current_trick[0].value:
            # On vérifie si ça complète le carré (Total 4)
            if self.rank_counter + played_count == 4:
                # Règle anti "3+1" : On doit jouer au moins autant de cartes que la table
                if played_count >= current_trick_count: 
                     is_interception = True
                
        # 3. Vérification du tour (si pas interception)
        if not is_interception:
            if player_index != self.current_player_index:
                return False, "Ce n'est pas votre tour !"

        # 4. Validation par rapport à la table
        if self.current_trick:
            # Cas A : MÊME RANG (Potentiel de compléter le carré)
            if cards[0].value == self.current_trick[0].value:
                
                # --- MODIFICATION ICI POUR "1 1 2" ---
                if played_count != current_trick_count:
                    # On autorise la différence SEULEMENT si :
                    # 1. La somme totale atteint 4 (rank_counter inclut déjà les cartes précédentes)
                    # 2. On ne joue pas moins de cartes que la table (Interdit de finir un 3 par un 1)
                    
                    is_valid_completion = (self.rank_counter + played_count == 4) and (played_count >= current_trick_count)
                    
                    if not is_valid_completion:
                         return False, f"Il faut jouer {current_trick_count} cartes (sauf pour finir un carré)."

                # Mise à jour du compteur
                self.rank_counter += played_count
                
                # Si on atteint 4 cartes -> COUPE !
                if self.rank_counter >= 4:
                    return self._handle_cut(player_index, cards, "CARRÉ COMPLÉTÉ !")
                
            # Cas B : RANG SUPÉRIEUR
            elif cards[0].value > self.current_trick[0].value:
                if played_count != current_trick_count:
                    return False, f"Il faut jouer {current_trick_count} cartes."
                self.rank_counter = played_count # Reset
                
            # Cas C : RANG INFÉRIEUR
            else:
                return False, "Carte trop faible."
        else:
            # Table vide
            self.rank_counter = played_count

        # --- APPLICATION DU COUP ---
        player = self.players[player_index]
        player.remove_cards(cards)
        self.current_trick = cards
        self.trick_owner = player_index

        if not player.hand:
            player.has_finished = True
            self.winners.append(player)

        self._next_player()
        return True, "Coup joué"

    def _handle_cut(self, player_index, cards, reason):
        """Helper pour gérer la coupe (nettoyage de table)"""
        player = self.players[player_index]
        player.remove_cards(cards)
        
        # Victoire ?
        if not player.hand:
            player.has_finished = True
            self.winners.append(player)
            self.current_trick = []
            self.trick_owner = None
            self.rank_counter = 0
            self._next_player()
            return True, f"{reason} (et fini !)"

        # Le joueur rejoue
        self.current_trick = []
        self.trick_owner = None
        self.rank_counter = 0 # Table vide = 0 cartes
        self.current_player_index = player_index # Il garde la main
        
        return True, f"COUPE ! {reason} Vous rejouez."

    def _pass_turn(self):
        self._next_player()
        if self.current_player_index == self.trick_owner:
            self.current_trick = []
            self.rank_counter = 0 # Reset si le tour revient au maître
        return True, "Tour passé"

    def _next_player(self):
        original_index = self.current_player_index
        while True:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            if self.current_player_index == original_index and self.players[original_index].has_finished:
                break 
            if not self.players[self.current_player_index].has_finished:
                break


 
    