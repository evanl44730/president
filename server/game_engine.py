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
        
        self.forced_rank_active = False

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
        self.forced_rank_active = False # Reset
        
        for i, player in enumerate(self.players):
            player.hand = []
            player.has_finished = False
            player.add_cards(hands[i])
        
        # Pour le MVP, le joueur 0 commence toujours (ou celui avec 3 de coeur en V2)
        self.current_player_index = 0

    def play_move(self, player_index, cards):
        """
        Gère le coup avec : Règle du 2 (Bombe), Coupes, 1-1-2, et règle "Ou rien".
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
            if self.rank_counter + played_count == 4:
                if played_count >= current_trick_count: 
                     is_interception = True
        
        # 3. Vérification du tour
        if not is_interception:
            if player_index != self.current_player_index:
                return False, "Ce n'est pas votre tour !"

        # 4. Validation par rapport à la table
        set_next_forced = False 

        if self.current_trick:
            # --- Vérification de la contrainte "Ou Rien" ---
            if self.forced_rank_active:
                if cards[0].value != self.current_trick[0].value:
                    return False, "Bloqué : Le joueur précédent vous oblige à jouer la même carte ou passer."

            # Cas A : MÊME RANG
            if cards[0].value == self.current_trick[0].value:
                # Vérification validité (Règle 1-1-2 et anti 3+1)
                is_valid_completion = (self.rank_counter + played_count == 4) and (played_count >= current_trick_count)
                
                if played_count != current_trick_count and not is_valid_completion:
                     return False, f"Il faut jouer {current_trick_count} cartes."

                self.rank_counter += played_count
                set_next_forced = True
                
            # Cas B : RANG SUPÉRIEUR
            elif cards[0].value > self.current_trick[0].value:
                if played_count != current_trick_count:
                    # Règle standard : le 2 doit aussi respecter le nombre de cartes
                    # Ex: Sur 2 Dames, il faut mettre 2 Deux.
                    return False, f"Il faut jouer {current_trick_count} cartes."
                
                self.rank_counter = played_count
                set_next_forced = False
                
            # Cas C : RANG INFÉRIEUR
            else:
                return False, "Carte trop faible."
        else:
            # Table vide
            self.rank_counter = played_count
            set_next_forced = False

        # --- NOUVEAU : RÈGLE DU 2 (La Bombe) ---
        # Si le coup est valide et que c'est un 2, ça coupe TOUT DE SUITE.
        if cards[0].rank == '2':
             return self._handle_cut(player_index, cards, "BOMBE (2) ! COUPÉ !")

        # --- VÉRIFICATION CARRÉ (4 cartes) ---
        if self.rank_counter >= 4:
             return self._handle_cut(player_index, cards, "CARRÉ COMPLÉTÉ !")

        # --- APPLICATION STANDARD ---
        player = self.players[player_index]
        player.remove_cards(cards)
        self.current_trick = cards
        self.trick_owner = player_index

        if not player.hand:
            player.has_finished = True
            self.winners.append(player)

        self.forced_rank_active = set_next_forced
        self._next_player()
        
        msg = "Coup joué"
        if self.forced_rank_active:
            msg += " (Le prochain joueur est bloqué !)"
            
        return True, msg

    def _handle_cut(self, player_index, cards, reason):
        # ... (Identique à avant)
        player = self.players[player_index]
        player.remove_cards(cards)
        
        if not player.hand:
            player.has_finished = True
            self.winners.append(player)
            self.current_trick = []
            self.trick_owner = None
            self.rank_counter = 0
            self.forced_rank_active = False
            self._next_player()
            return True, f"{reason} (et fini !)"

        self.current_trick = []
        self.trick_owner = None
        self.rank_counter = 0
        self.forced_rank_active = False
        self.current_player_index = player_index 
        
        return True, f"{reason} Vous rejouez."

    def _handle_cut(self, player_index, cards, reason):
        player = self.players[player_index]
        player.remove_cards(cards)
        
        if not player.hand:
            player.has_finished = True
            self.winners.append(player)
            self.current_trick = []
            self.trick_owner = None
            self.rank_counter = 0
            self.forced_rank_active = False
            self._next_player()
            return True, f"{reason} (et fini !)"

        self.current_trick = []
        self.trick_owner = None
        self.rank_counter = 0
        self.forced_rank_active = False
        self.current_player_index = player_index 
        
        return True, f"COUPE ! {reason} Vous rejouez."

    def _pass_turn(self):
        """Le joueur passe. Gestion du retour au propriétaire du pli."""
        # Passer annule toujours la contrainte "Ou rien"
        self.forced_rank_active = False 
        
        # On passe au joueur suivant
        self._next_player()
        
        # --- LOGIQUE DE RETOUR À L'ENVOYEUR ---
        
        # Cas 1 : Le tour revient au joueur qui a posé les cartes (et il est toujours en jeu)
        if self.current_player_index == self.trick_owner:
            self.current_trick = []
            self.rank_counter = 0
            # Le message sera envoyé au joueur qui récupère la main
            return True, "Tout le monde a passé. Vous remportez le pli et relancez !"

        # Cas 2 : Le joueur qui avait la main a FINI ses cartes et est sorti du jeu.
        # Dans ce cas, _next_player() l'a sauté. On doit détecter qu'on a fait un tour complet.
        # (Pour le MVP, on simplifie : si on est le seul survivant ou si ça tourne à vide, on vide la table).
        # Une astuce simple : Si le trick_owner a fini, on considère que le pli est gagné par le prochain actif.
        
        if self.trick_owner is not None:
            owner_player = self.players[self.trick_owner]
            if owner_player.has_finished:
                # Si l'ancien propriétaire est sorti, on regarde si on est revenu "juste après lui"
                # C'est un peu complexe à détecter parfaitement sans historique, 
                # mais pour ce MVP, si personne ne joue, le pli finira par être vidé quand quelqu'un coupera ou finira.
                # Pour l'instant, le Cas 1 suffit pour ton scénario "Je joue 3 Rois, je rejoue".
                pass

        return True, "Tour passé"

    def _next_player(self):
        """Calcule le prochain joueur et gère l'Auto-Pass si 'Ou Rien' actif."""
        original_index = self.current_player_index
        
        while True:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            
            # Condition d'arrêt pour éviter boucle infinie si tout le monde a fini
            if self.current_player_index == original_index and self.players[original_index].has_finished:
                break 
            
            # On s'arrête sur un joueur qui n'a PAS fini
            if not self.players[self.current_player_index].has_finished:
                break

        # Logique Auto-pass (étape précédente)
        if self.forced_rank_active and self.current_trick:
            player = self.players[self.current_player_index]
            required_value = self.current_trick[0].value
            has_matching_card = any(c.value == required_value for c in player.hand)
            
            if not has_matching_card:
                print(f"Auto-pass : {player.name} n'a pas de {self.current_trick[0].rank}")
                self._pass_turn()


 
    