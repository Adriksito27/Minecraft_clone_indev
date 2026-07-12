import unittest
from unittest.mock import patch

import main


class FakeNodePath:
    def __init__(self, name):
        self._name = name

    def getPythonTag(self, _name):
        return self

    def getName(self):
        return self._name


class FakeEntry:
    def __init__(self, node_path):
        self._node_path = node_path

    def getIntoNodePath(self):
        return self._node_path


class FakeRayQueue:
    def __init__(self, node_path):
        self._entry = FakeEntry(node_path)

    def getNumEntries(self):
        return 1

    def sortEntries(self):
        return None

    def getEntry(self, _index):
        return self._entry


class FakeTaskMgr:
    def add(self, *args, **kwargs):
        return None

    def remove(self, *args, **kwargs):
        return None

    def hasTaskNamed(self, *args, **kwargs):
        return False


class FakeImage:
    def __init__(self, *args, **kwargs):
        self._shown = True

    def hide(self):
        self._shown = False

    def show(self):
        self._shown = True

    def destroy(self):
        self._shown = False

    def isEmpty(self):
        return False

    def setTransparency(self, *args, **kwargs):
        return None

    def setBin(self, *args, **kwargs):
        return None

    def clearBin(self):
        return None

    def setPos(self, *args, **kwargs):
        return None

    def setScale(self, *args, **kwargs):
        return None


class CraftingUiTests(unittest.TestCase):
    def test_handle_right_click_opens_crafting_ui(self):
        game = main.MyGame.__new__(main.MyGame)
        game.inventoryOpen = False
        game.using_3x3 = False
        game.refreshInventoryVisuals = lambda: None
        game.placeBlock = lambda: (_ for _ in ()).throw(AssertionError("placeBlock should not run"))
        game.rayQueue = FakeRayQueue(FakeNodePath("crafting Table"))
        game.setupInventoryUI = lambda: setattr(game, 'inventoryOpen', True)

        game.handleRightClick()

        self.assertTrue(game.inventoryOpen)
        self.assertTrue(game.using_3x3)

    def test_setup_inventory_keeps_3x3_mode_when_opening_crafting_table(self):
        game = main.MyGame.__new__(main.MyGame)
        game.inventoryOpen = False
        game.using_3x3 = True
        game.releaseMouse = lambda: None
        game.taskMgr = FakeTaskMgr()
        game.hotbarBg = None
        game.selector_ui = None
        game.blockText = None
        game.crosshairs = None
        game.craftingTableBg = FakeImage()
        game.InventoryBg = None
        game.itemImagesUI = [None] * 9
        game.upperInventoryItems = [{"type": "", "count": 0} for _ in range(27)]
        game.upperItemImagesUI = [None] * 27
        game.itemIcons = {}
        game.acceptOnce = lambda *args, **kwargs: None
        game.refreshInventoryVisuals = lambda: None
        game.setup3x3UI = lambda: setattr(game, 'using_3x3', True)
        game.aspect2d = object()

        with patch.object(main, 'OnscreenImage', FakeImage):
            game.setupInventoryUI()

        self.assertTrue(game.inventoryOpen)
        self.assertTrue(game.using_3x3)


if __name__ == '__main__':
    unittest.main()
