import pytest
from src.engine.scripts import distribute_roles, TROUBLE_BREWING
from src.engine.roles.base_role import get_role_class
from src.state.game_state import RoleType

def test_distribution_counts():
    # Test for various player counts
    for count in range(5, 16):
        roles = distribute_roles(TROUBLE_BREWING, count)
        assert len(roles) == count
        
        # Count types
        counts = {RoleType.TOWNSFOLK: 0, RoleType.OUTSIDER: 0, RoleType.MINION: 0, RoleType.DEMON: 0}
        for rid in roles:
            cls = get_role_class(rid)
            counts[cls.get_definition().role_type] += 1
            
        print(f"Count {count}: {counts}")
        # Demon should always be 1 for current script
        assert counts[RoleType.DEMON] == 1
        
        # Verify Minion count
        if count <= 6:
            assert counts[RoleType.MINION] == 1
        elif count <= 9:
            assert counts[RoleType.MINION] == 1
        elif count <= 12:
            assert counts[RoleType.MINION] == 2
        else:
            assert counts[RoleType.MINION] == 3

def test_baron_effect():
    # Force Baron to be in play if possible
    # We'll just run distribution multiple times until Baron appears or check the logic
    for _ in range(100):
        roles = distribute_roles(TROUBLE_BREWING, 7)
        if "baron" in roles:
            counts = {RoleType.TOWNSFOLK: 0, RoleType.OUTSIDER: 0, RoleType.MINION: 0, RoleType.DEMON: 0}
            for rid in roles:
                cls = get_role_class(rid)
                counts[cls.get_definition().role_type] += 1
            
            # Normal 7 player: 5 Town, 0 Outsider, 1 Minion, 1 Demon
            # With Baron: 3 Town, 2 Outsider, 1 Minion, 1 Demon
            assert counts[RoleType.TOWNSFOLK] == 3
            assert counts[RoleType.OUTSIDER] == 2
            break
