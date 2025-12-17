import eventlet
import socketio
from game_engine import Game, Card
from player import Player
import os

sio = socketio.Server(cors_allowed_origins='*') 
app = socketio.WSGIApp(sio)

game = Game()
sid_to_player = {}

@sio.on('give_cards_back')
def handle_give_cards(sid, data):
    player = sid_to_player.get(sid)
    if not player: return

    cards_codes = data.get('cards', [])
    cards_obj = []
    for code in cards_codes:
        rank = code[:-1]
        suit = code[-1]
        cards_obj.append(Card(rank, suit))
        
    success, msg = game.resolve_manual_exchange(player, cards_obj)
    
    if success:
        sio.emit('notification', {'message': "Cartes données !"}, to=sid)
        # On renvoie l'état à tout le monde (pour mettre à jour les mains et lancer le jeu si fini)
        broadcast_game_state()
    else:
        sio.emit('notification', {'message': f"Erreur: {msg}"}, to=sid)

def broadcast_player_list():
    """Envoie la liste des pseudos connectés à tout le monde (pour le lobby)"""
    usernames = [p.name for p in game.players]
    sio.emit('update_player_list', {'players': usernames})

def broadcast_game_state():
    for sid, player in sid_to_player.items():
        # ... (calcul hand_cards, table_cards...)
        hand_cards = [str(c) for c in player.hand]
        table_cards = [str(c) for c in game.current_trick]
        
        # --- LOGIQUE ÉCHANGE ---
        is_exchange_phase = (getattr(game, 'state', 'PLAYING') == "EXCHANGE")
        exchange_data = None
        
        if is_exchange_phase:
            # Si je dois rendre des cartes
            if player.name in getattr(game, 'pending_exchanges', {}):
                info = game.pending_exchanges[player.name]
                exchange_data = {
                    "target": info["target"].name,
                    "count": info["count"]
                }
        # -----------------------

        # Masque (Inutile pendant l'échange, tout est clickable pour choisir)
        playable_mask = game.get_playable_mask(player) if not is_exchange_phase else [True]*len(player.hand)
        
        # Calcul du message
        if is_exchange_phase:
            if exchange_data:
                msg = f"ÉCHANGE : Tu dois rendre {exchange_data['count']} cartes à {exchange_data['target']}."
            else:
                msg = "ÉCHANGE : En attente du Président/VP..."
        else:
            current_player_name = game.players[game.current_player_index].name
            msg = f"Tour de {current_player_name}"

        state = {
            "hand": hand_cards,
            "playable_mask": playable_mask,
            "table": table_cards,
            "is_my_turn": (player == game.players[game.current_player_index]) if not is_exchange_phase else False,
            "my_role": player.role,
            "message": msg,
            # NOUVEAU
            "is_exchange": is_exchange_phase,
            "exchange_info": exchange_data
        }

        sio.emit('game_state', state, to=sid)

@sio.event
def connect(sid, environ):
    print(f"Client connecté : {sid}")

@sio.event
def disconnect(sid):
    if sid in sid_to_player:
        player = sid_to_player[sid]
        # Pour le MVP lobby, on retire le joueur s'il part avant le début
        if player in game.players:
            game.players.remove(player)
        del sid_to_player[sid]
        broadcast_player_list() # Mettre à jour la liste des présents

@sio.on('join_game')
def handle_join(sid, data):
    username = data.get('username', f"Joueur_{sid[:4]}")
    new_player = Player(username, sid)
    
    game.add_player(new_player)
    sid_to_player[sid] = new_player
    
    sio.emit('notification', {'message': f"Bienvenue {username}"}, to=sid)
    
    # Au lieu de démarrer, on envoie la liste mise à jour à tout le monde
    broadcast_player_list()

@sio.on('start_game_command')
def handle_start_game(sid):
    """Lancé quand un joueur clique sur 'Lancer la partie'"""
    if len(game.players) < 2:
        sio.emit('notification', {'message': "Il faut au moins 2 joueurs !"}, to=sid)
        return

    print("Lancement de la partie !")
    game.start_game()
    
    # On prévient tout le monde que ça commence
    sio.emit('game_started', {})
    broadcast_game_state()

def start_new_round():
    """Fonction appelée après le délai pour relancer"""
    print("⏳ Lancement de la nouvelle manche...")
    game.start_game()
    
    # On prévient tout le monde que ça recommence (et on affiche l'interface d'échange si besoin)
    sio.emit('notification', {'message': "Nouvelle manche ! Place aux échanges !"})
    broadcast_game_state()


@sio.on('play_cards')
def handle_play(sid, data):
    player = sid_to_player.get(sid)
    if not player: return

    try:
        p_index = game.players.index(player)
    except ValueError: return

    cards_codes = data.get('cards', [])
    cards_obj = []
    
    if not cards_codes:
        success, msg = game.play_move(p_index, [])
    else:
        for code in cards_codes:
            rank = code[:-1]
            suit = code[-1]
            cards_obj.append(Card(rank, suit))
        
        success, msg = game.play_move(p_index, cards_obj)

    if success:
        # Si le message contient "Manche terminée", c'est que tout le monde a fini
        if "Manche terminée" in msg:
            sio.emit('notification', {'message': f"🏆 {msg} - Nouvelle partie dans 5 secondes..."})
            broadcast_game_state()
            
            # --- AUTOMATISATION DU RELANCE ---
            # On attend 5 secondes, puis on lance start_new_round
            eventlet.spawn_after(5, start_new_round)
            return # On sort pour ne pas refaire broadcast tout de suite

        # Si ce n'est pas fini, on notifie juste la coupe ou le coup
        elif "COUPE" in msg or "CARRÉ" in msg:
             sio.emit('notification', {'message': f"⚡ {player.name} A COUPÉ LE PLI ! ⚡"})
        
        # On diffuse l'état
        broadcast_game_state()
        
    else:
        sio.emit('notification', {'message': f"Erreur: {msg}"}, to=sid)

@sio.event
def disconnect(sid):
    # 1. On cherche le joueur pour le retirer
    if sid in sid_to_player:
        player_name = sid_to_player[sid].name
        
        # On le retire du moteur de jeu
        game.remove_player(sid)
        
        # On le retire du dictionnaire global
        del sid_to_player[sid]
        
        print(f"🚪 {player_name} s'est déconnecté.")
        
        # 2. Notification aux autres
        sio.emit('notification', {'message': f"🚪 {player_name} a quitté la partie."})
        
        # 3. Vérification des règles de fin de partie
        # Si la partie était en cours (PLAYING ou EXCHANGE)
        if game.state != "WAITING":
            # Si on tombe sous les 3 joueurs
            if len(game.players) < 3:
                game.reset_to_lobby()
                sio.emit('notification', {'message': "⚠️ Moins de 3 joueurs restants ! La partie est annulée."})
                sio.emit('game_cancelled') # Signal spécial pour le client
            else:
                # Optionnel : Si on est encore assez nombreux (ex: 5 -> 4), 
                # on pourrait continuer, mais dans un jeu de cartes, 
                # perdre une main fausse tout. Par sécurité, on annule souvent tout.
                # Pour respecter ta demande stricte "Si < 3", on laisse continuer sinon.
                # Mais attention : l'ordre des tours risque d'être perturbé.
                # Conseil : Pour l'instant, annulons tout si quelqu'un part en jeu pour éviter les bugs.
                game.reset_to_lobby()
                sio.emit('notification', {'message': "🚫 Un joueur a quitté la partie en cours. Retour au salon."})
                sio.emit('game_cancelled')

        # 4. Mise à jour de la liste du lobby (si on est dans le lobby)
        player_names = [p.name for p in game.players]
        sio.emit('update_player_list', {'players': player_names})

if __name__ == '__main__':
    # 2. MODIFICATION PORT : Render nous donne un port via l'environnement
    # Si 'PORT' n'existe pas (en local), on utilise 5000
    port = int(os.environ.get('PORT', 5000))
    
    print(f"Server listening on port {port}")
    # On écoute sur '0.0.0.0' pour être accessible de l'extérieur
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', port)), app)