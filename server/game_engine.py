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
    
    def remove_player(self, sid):
        """Retire un joueur du jeu via son ID de session."""
        player_to_remove = None
        for p in self.players:
            if p.sid == sid:
                player_to_remove = p
                break
        
        if player_to_remove:
            self.players.remove(player_to_remove)
            
            # Si c'était au tour de ce joueur, on passe au suivant pour pas bloquer
            if self.state == "PLAYING" and self.current_player_index >= len(self.players):
                self.current_player_index = 0
            
            return player_to_remove
        return None

    def reset_to_lobby(self):
        """Annule la partie en cours et remet tout le monde en attente."""
        self.state = "WAITING"
        self.current_trick = []
        self.trick_owner = None
        self.rank_counter = 0
        self.winners = []
        self.pending_exchanges = {}
        
        # On vide les mains des joueurs restants
        for p in self.players:
            p.hand = []
            p.has_finished = False
            # On garde les rôles ? Discutable. Pour l'instant on reset pas les rôles
            # pour ne pas frustrer, mais on pourrait : p.role = "Neutre"

    def start_game(self):
        """Lance une nouvelle manche avec gestion des rôles persistants."""
        self.deck = Deck()
        self.deck.shuffle()
        hands = self.deck.deal(len(self.players))
        
        # IMPORTANT : On ne reset PAS self.players (pour garder les rôles)
        
        # Reset de la table
        self.current_trick = []
        self.trick_owner = None
        self.rank_counter = 0
        self.forced_rank_active = False
        
        # On vide la liste des gagnants pour la NOUVELLE manche
        self.winners = [] 

        # Distribution
        for i, player in enumerate(self.players):
            player.hand = []
            player.has_finished = False
            player.add_cards(hands[i])

        # Gestion des échanges
        # On regarde les rôles ACTUELS (calculés à la fin de la partie d'avant)
        has_roles = any(p.role.startswith("Président") for p in self.players)
        
        if has_roles:
            print("Début phase échange...")
            self.state = "EXCHANGE"
            self.pending_exchanges = {}
            self._apply_forced_exchanges() # TdC donne ses cartes au Président
        else:
            self.state = "PLAYING"
            # Si pas de rôle (1ère partie), joueur 0 commence ou TdC commence
            # Règle usuelle : le TdC de la partie d'avant commence.
            # On cherche le TdC
            tdc = next((p for p in self.players if "Trou du Cul" in p.role), None)
            if tdc:
                self.current_player_index = self.players.index(tdc)
            else:
                self.current_player_index = 0

    def _apply_forced_exchanges(self):
        """
        Applique l'échange OBLIGATOIRE (Les nuls donnent leurs meilleures cartes).
        """
        # Identifier les rôles
        pres = next((p for p in self.players if p.role == "Président 👑"), None)
        tdc = next((p for p in self.players if p.role == "Trou du Cul 💩"), None)
        
        vp = next((p for p in self.players if p.role == "Vice-Président 🎖️"), None)
        vtdc = next((p for p in self.players if p.role == "Vice-Trou du Cul 🧹"), None)

        # Règle 1 : TdC donne 2 meilleures cartes au Président
        if pres and tdc:
            # On trie la main (les meilleures sont à la fin)
            # Rappel: Card implémente __lt__ donc sort() marche (3..As..2)
            best_cards = tdc.hand[-2:] # Les 2 dernières
            
            # Transfert
            tdc.remove_cards(best_cards)
            pres.add_cards(best_cards)
            
            # On note que le Président doit rendre 2 cartes au TdC
            self.pending_exchanges[pres.name] = {"target": tdc, "count": 2}
            print(f"Échange auto : {tdc.name} donne {best_cards} à {pres.name}")

        # Règle 2 : Vice-TdC donne 1 meilleure carte au Vice-Président (si 5+ joueurs)
        if vp and vtdc:
            best_card = vtdc.hand[-1:] # La dernière (liste de 1 élément)
            
            vtdc.remove_cards(best_card)
            vp.add_cards(best_card)
            
            self.pending_exchanges[vp.name] = {"target": vtdc, "count": 1}
            print(f"Échange auto : {vtdc.name} donne {best_card} à {vp.name}")
            
        # Le premier joueur à jouer sera le TdC (règle classique : le TdC commence)
        # Ou le Président selon les variantes. Ici on va dire que le TdC commence pour se refaire.
        if tdc:
            self.current_player_index = self.players.index(tdc)

    def resolve_manual_exchange(self, player, cards):
        """
        Le Président/VP choisit les cartes à rendre.
        """
        if self.state != "EXCHANGE":
            return False, "Ce n'est pas le moment des échanges."

        if player.name not in self.pending_exchanges:
            return False, "Vous n'avez pas d'échange à faire."

        exchange_info = self.pending_exchanges[player.name]
        target_player = exchange_info["target"]
        count_needed = exchange_info["count"]

        if len(cards) != count_needed:
            return False, f"Vous devez choisir exactement {count_needed} cartes."

        # Transfert
        player.remove_cards(cards)
        target_player.add_cards(cards)
        
        # On supprime l'échange de la liste d'attente
        del self.pending_exchanges[player.name]
        
        # Si tous les échanges sont faits, on lance le jeu
        if not self.pending_exchanges:
            self.state = "PLAYING"
            return True, "Échange terminé ! La partie commence."
        
        return True, "Cartes envoyées. En attente des autres..."

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
            
            if len(self.winners) == 1:
                self.current_trick = []
                self.trick_owner = None
                self.rank_counter = 0
                self.forced_rank_active = False # On annule toute contrainte "Ou rien"
                
                # On passe la main au joueur suivant
                self._next_player()
                
                return True, f"👑 {player.name} a fini ! La table est vidée pour le suivant."

        self.forced_rank_active = set_next_forced
        self._next_player()
        
        msg = "Coup joué"
        if self.forced_rank_active:
            msg += " (Le prochain joueur est bloqué !)"
        
        active_players = [p for p in self.players if not p.has_finished]
        
        if len(active_players) <= 1:
            # Le dernier joueur a perdu
            if active_players:
                last_player = active_players[0]
                self.winners.append(last_player) # On l'ajoute en dernier
            
            # CALCUL DES RÔLES
            self.assign_roles()
            
            return True, "Manche terminée ! Les rôles ont été attribués."
            
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
    
    def get_playable_mask(self, player):
        """
        Génère le masque.
        Gère intelligemment le "Tour" :
        - À mon tour : Je peux jouer tout ce qui est valide.
        - Pas à mon tour : Je ne peux jouer QUE si ça coupe (Carré).
        """
        mask = []
        
        # Est-ce que c'est à ce joueur de jouer ?
        is_turn = (player == self.players[self.current_player_index])

        # Analyse de la table
        if not self.current_trick:
            # Table vide : Si c'est mon tour, tout est OK. Sinon, rien.
            return [is_turn] * len(player.hand)

        table_val = self.current_trick[0].value
        table_rank = self.current_trick[0].rank
        table_qty = len(self.current_trick)

        # Compte des cartes en main
        hand_counts = {}
        for c in player.hand:
            hand_counts[c.rank] = hand_counts.get(c.rank, 0) + 1

        for card in player.hand:
            is_playable = False
            my_qty = hand_counts[card.rank]

            # --- LOGIQUE UNIVERSELLE (Physique du jeu) ---
            # On calcule d'abord si le coup est techniquement valide
            
            valid_move = False
            is_interception_move = False # Pour savoir si c'est une coupe

            # A. Mode "Ou Rien"
            if self.forced_rank_active:
                if card.rank == table_rank:
                    # 1. Suivre
                    if my_qty >= table_qty: valid_move = True
                    # 2. Couper (Compléter carré)
                    needed = 4 - self.rank_counter
                    if (needed <= my_qty) and (needed >= table_qty): 
                        valid_move = True
                        is_interception_move = True

            # B. Jeu Normal
            else:
                # 1. Bombe (2)
                if card.rank == '2':
                    if my_qty >= table_qty: valid_move = True
                
                # 2. Même valeur
                elif card.value == table_val:
                    if my_qty >= table_qty: valid_move = True
                    
                    # Vérification Coupe (Carré)
                    needed = 4 - self.rank_counter
                    if (needed <= my_qty) and (needed >= table_qty):
                        valid_move = True
                        is_interception_move = True
                
                # 3. Valeur supérieure
                elif card.value > table_val:
                    if my_qty >= table_qty: valid_move = True

            # --- FILTRAGE SELON LE TOUR ---
            
            if is_turn:
                # Si c'est mon tour, tout coup valide est accepté
                if valid_move: is_playable = True
            else:
                # Si ce N'EST PAS mon tour, seule l'interception (Coupe) est acceptée
                if valid_move and is_interception_move:
                    is_playable = True
            
            mask.append(is_playable)
            
        return mask
    
    def assign_roles(self):
        """
        Attribue les rôles selon le classement (self.winners).
        3 joueurs : Pres, Neutre, TdC
        4 joueurs : Pres, Neutre, Neutre, TdC
        5 joueurs : Pres, Vice-Pres, Neutre, Vice-TdC, TdC
        """
        count = len(self.players)
        ranking = self.winners
        
        # Sécurité : si la liste n'est pas complète (bug), on ne fait rien
        if len(ranking) != count:
            return

        # 1. Reset tout le monde à "Neutre" par défaut
        for p in self.players:
            p.role = "Neutre"

        # 2. Le Premier est Président, le Dernier est Trou du Cul (Valable pour 3+)
        ranking[0].role = "Président 👑"
        ranking[-1].role = "Trou du Cul 💩"

        # 3. Gestion spécifique selon le nombre de joueurs
        if count == 3:
            # [Pres, Neutre, TdC] -> Déjà fait par le code ci-dessus
            pass
            
        elif count == 4:
            # [Pres, Neutre, Neutre, TdC] -> Déjà fait
            pass
            
        elif count >= 5:
            # [Pres, VP, ...Neutres..., Vice-TdC, TdC]
            ranking[1].role = "Vice-Président 🎖️"
            ranking[-2].role = "Vice-Trou du Cul 🧹"

        print("--- RÔLES ATTRIBUÉS ---")
        for p in ranking:
            print(f"{p.name} : {p.role}")


 
    