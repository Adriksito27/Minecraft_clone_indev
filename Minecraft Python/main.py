from math import pi, sin, cos
from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFile, CullFaceAttrib,loadPrcFileData
from panda3d.core import DirectionalLight, AmbientLight, BitMask32, TextNode
from panda3d.core import TransparencyAttrib
from panda3d.core import WindowProperties
from panda3d.core import CollisionTraverser, CollisionNode, CollisionBox, CollisionRay, CollisionHandlerQueue, CollisionHandlerPusher, CollisionCapsule
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import ClockObject
from noise import pnoise2
from direct.gui.DirectButton import DirectButton
import random
from direct.showbase.ShowBaseGlobal import aspect2d, render2d
from panda3d.core import Point3


loadPrcFile('settings.prc')
loadPrcFileData("", "sync-video false")

def degToRad(degrees):
    return degrees * (pi / 180.0)

class MyGame(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.chunksData = {}
        self.renderDistance = 1 
        self.activeVisualChunks = {}
        self.instanceRoot = self.render.attachNewNode("InstanceRoot")
        self.transparentChunk = self.render.attachNewNode('transparent-chunk')
        self.opaqueChunk = self.render.attachNewNode('opaque-chunk')
        self.craftingSlots2x2 = [{"type": "", "count": 0} for _ in range(4)]
        self.craftingSlots3x3 = [{"type": "", "count": 0} for _ in range(9)]
        self.craftingResultSlot = {"type": "", "count": 0}
        self.type = None
        self.seedX = random.randint(0, 100000)
        self.seedY = random.randint(0, 100000)
        self.hotbarItems = [{"type": "", "count": 0} for _ in range(9)]
        self.hotbarItems[0] = {"type": "crafting Table", "count": 1}
        self.upperInventoryItems = [{"type": "", "count": 0} for _ in range(27)]
        self.itemImagesUI = [None] * 9
        self.hotbarTextsUI = [None] * 9
        self.upperItemImagesUI = [None] * len(self.upperInventoryItems)
        self.upperInventoryTextsUI = [None] * len(self.upperInventoryItems)
        self.pusher = CollisionHandlerPusher()
        self.selectedBlockType = ''
        self.globalClock = ClockObject.getGlobalClock()
        self.loadModels()
        self.setupLights()
        self.generateChunk(0, 0)
        self.buildChunkVisual(0, 0)
        self.spawnPlayerOnSurface()
        self.setupFog()
        self.setFrameRateMeter(True) 
        self.setBackgroundColor(0.47, 0.65, 1.0)
        self.setupCamera()
        self.captureMouse()
        self.setupControls()
        self.setupHotbarUI()
        self.setupCrafting()
        self.craftingTableBg = OnscreenImage(
            image='crafting3x3UI.png'
        )
        self.craftingTableBg.hide()
        self.inventoryOpen = False
        self.using_3x3 = False
        self.draggedItemIndex = None
        self.draggedIcon = None
        self.taskMgr.add(self.update, 'update')
        self.globalClock = ClockObject.getGlobalClock()
        self.customFont = self.loader.loadFont('Minecraft.ttf')
        self.blockText = OnscreenText(
            text="", 
            pos=(0, -0.75),                  
            scale=0.07,                        
            fg=(1, 1, 1, 1),
            shadow=(0, 0, 0, 0.8),
            font=self.customFont,                            
            align=TextNode.ACenter,                            
            mayChange=True
        )
        self.render.setTwoSided(False)
        self.upperItemImagesUI = [None] * 27
        self.ui_start_x = -0.5241
        self.ui_slot_spacing = 0.131
        self.inv_start_x = -0.725
        self.inv_spacing = 0.18
        self.inv_z = -0.663
        self.upper_start_z = -0.440
        self.row_spacing_z = 0.175
        self.updateHandBlock()
        self.verticalVelocity = 0.0     # Velocidad en el eje Z
        self.gravity = -32.0            # Fuerza de la gravedad
        self.jumpForce = 14.0           # Fuerza del salto           
        self.isGrounded = True
        self.timeSinceGrounded = 0.0 
        self.taskMgr.add(self.updatePhysics, "updatePhysicsTask")
        self.droppedItems = []
        self.taskMgr.add(self.updateDroppedItems, "updateDroppedItemsTask")
        self.taskMgr.add(self.updateChunksTask, "UpdateChunksTask")
        self.taskMgr.add(self.lockPlayerRotationTask, "lockPlayerRotationTask")
        self.taskMgr.add(self.updatePlayerHeightTask, "updatePlayerHeightTask")

    def spawnPlayerOnSurface(self):
        # 1. Buscamos el bloque más alto en las coordenadas del centro del mundo (0, 0)
        cx, cy = 0, 0
        localX, localY = 0, 0
        
        highestZ = 0
        if (cx, cy) in self.chunksData:
            chunk = self.chunksData[(cx, cy)]
            # Filtramos las llaves del diccionario para encontrar la altura máxima en el origen
            matchingBlocks = [z for (bx, by, z) in chunk.keys() if bx == localX and by == localY]
            
            if matchingBlocks:
                maxZ = max(matchingBlocks)
                # Sumamos 4 unidades: 2 para llegar al tope del bloque y 2 extra para la altura de los ojos del jugador
                highestZ = (maxZ * 2) + 4
                
        # 2. Teletransportamos la cámara/jugador exactamente a esa altura segura
        self.camera.setPos(0, 0, highestZ)

    def lockPlayerRotationTask(self, task):      
        if self.playerNodePath:
            currentH = self.playerNodePath.getH(self.render)

            self.playerNodePath.setHpr(self.render, currentH, 0, 0)
        
        return task.cont
 
    def updatePhysics(self, task):
        if getattr(self, 'inventoryOpen', False):
            return task.cont

        dt = self.globalClock.getDt()
        if dt > 0.05:  
            dt = 0.05

        old_z = self.camera.getZ()

        self.verticalVelocity += (self.gravity * 2.5) * dt

        if self.verticalVelocity < -50.0:
            self.verticalVelocity = -50.0
        
        # Desplazamos la cámara en vertical
        self.camera.setZ(old_z + self.verticalVelocity * dt)

        self.cTrav.traverse(self.render)

       
        # Comparamos la altura real tras el traverse. Si la Z real es mayor que
        # la Z a la que intentábamos caer, el pusher nos ha levantado porque hay un bloque debajo.
        actual_z = self.camera.getZ()
        expected_z = old_z + (self.verticalVelocity * dt)

        if actual_z > expected_z + 0.001 and self.verticalVelocity <= 0:
            self.isGrounded = True
            self.verticalVelocity = 0.0
            self.timeSinceGrounded = 0.0
            self.camera.setZ(actual_z)
        else:
            # Si caminamos al vacío, caemos de forma instantánea al siguiente nivel o al abismo
            self.isGrounded = False
            self.timeSinceGrounded += dt

        return task.cont

    def doJump(self):
        # Solo permitimos saltar si el jugador está pisando un bloque firme
        if getattr(self, 'isGrounded', False) and not getattr(self, 'inventoryOpen', False):
            # Le damos un impulso vertical positivo (puedes subir el 12.0 si salta poco)
            self.verticalVelocity = 20.0
            self.isGrounded = False    
    
    def updatePlayerHeightTask(self, task):
        playerX = self.camera.getX()
        playerY = self.camera.getY()
        playerZ = self.camera.getZ()
        
        # 1. Calculamos instantáneamente en qué bloque exacto estás parado
        gridX = int(playerX // 2)
        gridY = int(playerY // 2)
        
        cx = gridX // 16
        cy = gridY // 16
        localX = gridX % 16
        localY = gridY % 16
        
        highestZ = 0
        if (cx, cy) in self.chunksData:
            chunk = self.chunksData[(cx, cy)]
            
            # 2. OPTIMIZACIÓN CRÍTICA: En lugar de un bucle 'for' lento,
            # filtramos las llaves del diccionario para encontrar la Z más alta al instante
            matchingBlocks = [z for (bx, by, z) in chunk.keys() if bx == localX and by == localY]
            
            if matchingBlocks:
                maxZ = max(matchingBlocks)
                calculatedZ = (maxZ * 2) + 2
                if calculatedZ <= playerZ + 1.5:
                    highestZ = calculatedZ
                        
        if self.camera.getZ() < highestZ:
            self.camera.setZ(highestZ)
            
        return task.cont

    def update(self, task):
        
        dt = self.globalClock.getDt()
        playerMoveSpeed = 5

        x_movement = 0
        y_movement = 0
        
        z_movement = 0

        if self.cameraSwingActivated:
            if self.keyMap['forward']:
                x_movement -= dt * playerMoveSpeed * sin(degToRad(self.camera.getH()))
                y_movement += dt * playerMoveSpeed * cos(degToRad(self.camera.getH()))
            if self.keyMap['backward']:
                x_movement += dt * playerMoveSpeed * sin(degToRad(self.camera.getH()))
                y_movement -= dt * playerMoveSpeed * cos(degToRad(self.camera.getH()))
            if self.keyMap['left']:
                x_movement -= dt * playerMoveSpeed * cos(degToRad(self.camera.getH()))
                y_movement -= dt * playerMoveSpeed * sin(degToRad(self.camera.getH()))
            if self.keyMap['right']:
                x_movement += dt * playerMoveSpeed * cos(degToRad(self.camera.getH()))
                y_movement += dt * playerMoveSpeed * sin(degToRad(self.camera.getH()))
            if self.keyMap['up']:
                z_movement += dt * playerMoveSpeed
            if self.keyMap['down']:
                z_movement -= dt * playerMoveSpeed    
        
        self.camera.setPos(
            self.camera.getX() + x_movement,
            self.camera.getY() + y_movement,
            self.camera.getZ() + z_movement
        )
        
        if self.cameraSwingActivated:
            md = self.win.getPointer(0)
            mouseX = md.getX()
            mouseY = md.getY()

            mouseChangeX = mouseX - self.lastMouseX
            mouseChangeY = mouseY - self.lastMouseY

            self.cameraSwingFactor = 10
            currentH = self.camera.getH()
            currentP = self.camera.getP()
            globalH = self.camera.getH(self.render)

            self.camera.setHpr(
                currentH - mouseChangeX * dt * self.cameraSwingFactor,
                min(90, max(-90, currentP - mouseChangeY * dt * self.cameraSwingFactor)),
                0
            )
            self.playerNodePath.setH(self.render, globalH)
            self.playerNodePath.setP(0)
            self.lastMouseX = mouseX
            self.lastMouseY = mouseY
        return task.cont

    def updateInventoryUI(self, task):
        self.refreshInventoryVisuals()
        return task.cont

    def setSelectedBlockType(self, type):
        self.selectedBlockType = type
        self.blockText.setText(f"{type.capitalize()}")
    
    def updateHandBlock(self):
        if hasattr(self, 'hand_block') and self.hand_block:
            self.hand_block.removeNode()
       
        block_name = (self.selectedBlockType)
        if block_name not in ['stick','poppy']:
            self.hand_block = self.loader.loadModel(f"{block_name}-block.glb")
        else:
            self.hand_block = self.loader.loadModel(f"{block_name}-item.glb")

        self.hand_block.reparentTo(self.camera)
        self.hand_block.setTransparency(TransparencyAttrib.MAlpha)
        self.hand_block.setBin('transparent', 0)
        
        
        
        if block_name == "":
            self.hand_block.setPos(0.8, 1.4, -1)
            self.hand_block.setHpr(0, -75, -10) 
            self.hand_block.setScale(0.25)

        else:
            self.hand_block.setHpr(-15, 10, 5) 
            self.hand_block.setPos(1.2, 2.5, -0.8)
            self.hand_block.setScale(0.4)

        self.hand_block.setDepthTest(True)
        self.hand_block.setDepthWrite(True)
        self.hand_block.setBin("fixed", 10)
        self.hand_block.setDepthOffset(1)
        self.hand_block.setCollideMask(0)

    def generateChunk(self, cx, cy):
        if (cx, cy) in self.chunksData:
            return
            
        chunkBlocks = {}
        noiseScale = 0.167
        minHeight = 7
        maxHeight = 6

        # Guardamos temporalmente el world_data viejo para que tus funciones lean de ahí
        oldWorldData = getattr(self, 'world_data', {})
        self.world_data = chunkBlocks

        for x in range(16):
            for y in range(16):
                globalX = (cx * 16) + x
                globalY = (cy * 16) + y

                noise = pnoise2(
                    (globalX + self.seedX) * noiseScale, 
                    (globalY + self.seedY) * noiseScale, 
                    octaves=2, 
                    persistence=0.5
                )

                finalHeight = int(minHeight + ((noise + 1) / 2) * maxHeight)
                finalHeight = max(1, min(finalHeight, 14))

                for z in range(finalHeight):
                    if z == finalHeight - 1:
                        blockType = 'grass'
                    elif z >= finalHeight - 3:
                        blockType = 'dirt'
                    else:
                        blockType = 'stone'

                    chunkBlocks[(x, y, z)] = blockType

                if 2 <= x < 14 and 2 <= y < 14:
                    if random.random() < 0.04:
                        tooClose = False
                        for checkX in range(x - 3, x + 4):
                            for checkY in range(y - 3, y + 4):
                                if chunkBlocks.get((checkX, checkY, finalHeight)) == 'wood':
                                    tooClose = True
                                    break
                            if tooClose: break

                        if not tooClose:
                            self.generateTree(x, y, finalHeight)

                    if random.random() < 0.06:
                        if chunkBlocks.get((x, y, finalHeight - 1)) == 'grass':
                            self.generatePoppy(x, y, finalHeight)

        self.chunksData[(cx, cy)] = chunkBlocks
        
        # Restauramos la variable por compatibilidad si es necesario
        self.world_data = oldWorldData

    def buildChunkVisual(self, cx, cy):
        if (cx, cy) in self.activeVisualChunks:
            return

        chunkNode = self.render.attachNewNode(f"Visual_Chunk_{cx}_{cy}")
        blocks = self.chunksData.get((cx, cy), {})

        for (x, y, z), blockType in blocks.items():
            neighborCheckers = [
                (x, y, z + 1),     
                (x + 1, y, z),     
                (x - 1, y, z),     
                (x, y + 1, z),     
                (x, y - 1, z)      
            ]
            
            isBlockHidden = True
            for nx, ny, nz in neighborCheckers:
                neighborType = blocks.get((nx, ny, nz))
                if neighborType is None or neighborType in ['leaves', 'glass', 'poppy']:
                    isBlockHidden = False
                    break
            
            if isBlockHidden:
                continue

            realX = ((cx * 16) + x) * 2
            realY = ((cy * 16) + y) * 2
            realZ = z * 2
            
            self.createNewBlock(realX, realY, realZ, blockType, parentNode=chunkNode)

            # Creamos los colisionadores base del terreno dentro del propio chunkNode
            
            blockSolid = CollisionBox((realX, realY, realZ), 1, 1, 1)
            blockNode = CollisionNode('block-collision-node')
            blockNode.addSolid(blockSolid)
            blockNode.setIntoCollideMask(BitMask32.bit(1) | BitMask32.bit(2)) 
            collider = chunkNode.attachNewNode(blockNode)
            
            tempNode = chunkNode.attachNewNode('temp-placeholder')
            tempNode.setPos(realX, realY, realZ)
            tempNode.setName(blockType)
            collider.setPythonTag('owner', tempNode)

        self.activeVisualChunks[(cx, cy)] = chunkNode

    def updateChunksTask(self, task):
        if not hasattr(self, 'chunkTimer'):
            self.chunkTimer = 0.0
        
        self.chunkTimer += self.globalClock.getDt()
        if self.chunkTimer < 0.2:
            return task.cont
            
        self.chunkTimer = 0.0

        playerX = self.camera.getX()
        playerY = self.camera.getY()
        
        blockX = playerX / 2.0
        blockY = playerY / 2.0
        
        currentCx = int(blockX // 16)
        currentCy = int(blockY // 16)
        
        offsetX = 1 if (blockX % 16) >= 8 else -1
        offsetY = 1 if (blockY % 16) >= 8 else -1

        chunksToKeep = {
            (currentCx, currentCy),           
            (currentCx + offsetX, currentCy),  
            (currentCx, currentCy + offsetY),  
            (currentCx + offsetX, currentCy + offsetY) 
        }
        
        for targetCx, targetCy in chunksToKeep:
            if (targetCx, targetCy) not in self.chunksData:
                self.generateChunk(targetCx, targetCy)
                return task.cont 

        for targetCx, targetCy in chunksToKeep:
            if (targetCx, targetCy) not in self.activeVisualChunks:
                self.rebuildChunkVisuals(targetCx, targetCy)
                return task.cont 

        currentChunks = list(self.activeVisualChunks.keys())
        for cx, cy in currentChunks:
            if (cx, cy) not in chunksToKeep:
                if (cx, cy) in self.activeVisualChunks and self.activeVisualChunks[(cx, cy)]:
                    self.activeVisualChunks[(cx, cy)].removeNode()
                del self.activeVisualChunks[(cx, cy)]

        return task.cont

    def generateTree(self, tx, ty, base_z):
        trunk_height = random.randint(4, 6)
        
        # 1. Registrar el tronco de madera en los datos lógicos del mundo
        for z in range(base_z, base_z + trunk_height):
            self.world_data[(tx, ty, z)] = 'wood'
            
        # 2. Registrar las hojas en los datos lógicos del mundo
        leaves_start_z = base_z + trunk_height - 2
        for lz in range(leaves_start_z, leaves_start_z + 3):
            radius = 2 if lz < leaves_start_z + 2 else 1
            
            for lx in range(tx - radius, tx + radius + 1):
                for ly in range(ty - radius, ty + radius + 1):
                    if 0 <= lx < 16 and 0 <= ly < 16:
                        # No sobrescribir el tronco
                        if (lx == tx and ly == ty and lz < base_z + trunk_height):
                            continue
                        # Omitir esquinas aleatoriamente
                        if radius == 2 and (abs(lx - tx) == 2 and abs(ly - ty) == 2) and random.random() < 0.5:
                            continue
                        
                        # Guardar la hoja en el diccionario si el espacio está vacío
                        if (lx, ly, lz) not in self.world_data:
                            self.world_data[(lx, ly, lz)] = 'leaves'

    def generatePoppy(self, x, y, base_z):
        if self.world_data.get((x, y, base_z)) is None:
            self.world_data[(x, y, base_z)] = 'poppy'

    def setupInventoryUI(self):

        if not hasattr(self, 'inventoryOpen'):
            self.inventoryOpen = False

        if not self.inventoryOpen:
            self.inventoryOpen = True
            self.releaseMouse() 
            self.taskMgr.add(self.updateInventoryUI, "updateInventoryUI")
            
            # Ocultamos la Hotbar pequeña y su selector
            if hasattr(self, 'hotbarBg') and self.hotbarBg:
                self.hotbarBg.hide()
            if hasattr(self, 'selector_ui') and self.selector_ui:
                self.selector_ui.hide()

            if hasattr(self, 'blockText') and self.blockText:
                self.blockText.hide()
                self.crosshairs.hide()

            if not self.using_3x3:    
                self.InventoryBg = OnscreenImage(
                    image='inventory.png',
                    pos=(0, 0, 0),
                    scale=(1, 1, 1),
                    parent=self.aspect2d
                 )
                self.InventoryBg.setTransparency(TransparencyAttrib.MAlpha)
                self.InventoryBg.setBin('fixed', 1)
                if self.craftingTableBg and not self.craftingTableBg.isEmpty():
                    self.craftingTableBg.hide()
            else:
                self.setup3x3UI()
                if self.craftingTableBg and not self.craftingTableBg.isEmpty():
                    self.craftingTableBg.show()

            if not self.using_3x3:
                self.inv_start_x = -0.725
                self.inv_spacing = 0.18
                self.inv_z = -0.663
            else:
                self.inv_start_x = -0.7
                self.inv_spacing = 0.1735
                self.inv_z = -0.69
            
            if hasattr(self, 'itemImagesUI'):
                for slot_index, icon in enumerate(self.itemImagesUI):
                    # Añadimos comprobación por si el slot de la imagen contiene un None
                    if icon:
                        new_x = self.inv_start_x + (slot_index * self.inv_spacing)
                        icon.setPos(new_x, 0, self.inv_z)
                        icon.setScale(0.063, 1, 0.063) 
                        icon.setBin('fixed', 10) 

            if not self.using_3x3:
                self.upper_start_z = -0.440  # Primera fila encima de la hotbar
                self.row_spacing_z = 0.175  # Distancia vertical entre filas
            else:
                self.upper_start_z = -0.4620401859283447  # Primera fila encima de la hotbar
                self.row_spacing_z = 0.1829266548156738  # Distancia vertical entre filas

            self.upperItemImagesUI = []
            for index, item_name in enumerate(self.upperInventoryItems):
                # Extraemos el tipo de bloque del diccionario para no romper tus variables
                if item_name["type"] != "":
                    col = index % 9
                    row = index // 9
                    
                    slot_x = self.inv_start_x + (col * self.inv_spacing)
                    slot_z = self.upper_start_z + (row * self.row_spacing_z)
                    
                    # Buscamos la ruta usando la propiedad de texto interna del diccionario
                    icon = OnscreenImage(
                        image=self.itemIcons[item_name["type"]],
                        pos=(slot_x, 0, slot_z),
                        scale=(0.063, 1, 0.063),
                        parent=self.aspect2d
                    )
                    icon.setTransparency(TransparencyAttrib.MAlpha)
                    icon.setBin('fixed', 10)
                    self.upperItemImagesUI.append(icon)
                else:
                    self.upperItemImagesUI.append(None)

            self.acceptOnce('e', self.setupInventoryUI)
        
        else:
            self.inventoryOpen = False
            self.using_3x3 = False
            
            if hasattr(self, 'upperItemImagesUI'):
                for icon in self.upperItemImagesUI:
                    if icon:
                        icon.destroy()
                self.upperItemImagesUI = []

            if hasattr(self, 'InventoryBg') and self.InventoryBg:
                self.InventoryBg.destroy()
                self.craftingTableBg.destroy()
                self.InventoryBg = None
                self.taskMgr.remove('updateInventoryUI')

            if hasattr(self, 'craftingImagesUI') and self.craftingImagesUI:
                for icon in self.craftingImagesUI:
                    if icon:
                        icon.destroy()
                self.craftingImagesUI = []

            if hasattr(self, 'craftingTextsUI') and self.craftingTextsUI:
                for text in self.craftingTextsUI:
                    if text:
                        text.destroy()
                self.craftingTextsUI = []

            if hasattr(self, 'craftingResultImageUI') and self.craftingResultImageUI:
                self.craftingResultImageUI.destroy()
                self.craftingResultImageUI = None

            if hasattr(self, 'craftingResultTextUI') and self.craftingResultTextUI:
                self.craftingResultTextUI.destroy()
                self.craftingResultTextUI = None
        
            if hasattr(self, 'hotbarBg') and self.hotbarBg:
                self.hotbarBg.show()

            if hasattr(self, 'selector_ui') and self.selector_ui:
                self.selector_ui.show()

            if hasattr(self, 'blockText') and self.blockText:
                self.blockText.show()

            if hasattr(self, 'itemImagesUI'):
                for slot_index, icon in enumerate(self.itemImagesUI):
                    if icon: # Verificación de seguridad
                        original_x = self.ui_start_x + (slot_index * self.ui_slot_spacing)
                        icon.setPos(original_x, 0, -0.85)  
                        icon.setScale(0.045, 1, 0.045)  
                        icon.clearBin() 

            self.captureMouse()
            self.acceptOnce('e', self.setupInventoryUI)

            current_slot = getattr(self, 'selected_slot', 0)
            if 0 <= current_slot < len(self.hotbarItems):
                new_block = self.hotbarItems[current_slot]
                self.changeItem(new_block, current_slot)

            if hasattr(self, 'draggedIcon') and self.draggedIcon:
                self.draggedIcon.destroy()
                self.draggedIcon = None
                self.draggedItemIndex = None
                self.taskMgr.remove('updateDraggedItemTask')

            if hasattr(self, 'crosshairs') and self.crosshairs:
                self.crosshairs.show()
            self.refreshInventoryVisuals()

    def setup3x3UI(self):

        self.craftingTableBg = OnscreenImage(
            image="crafting3x3UI.png",
            pos=(0, 0, 0),
            scale=(0.85, 1, 0.85),
            parent=self.aspect2d
        )
        self.using_3x3 = True
        self.craftingTableBg.show()
        self.craftingTableBg.setBin('fixed', 2)
        self.craftingTableBg.setTransparency(TransparencyAttrib.MAlpha)

        self.refreshInventoryVisuals()

    def setupCrafting(self):
        self.crafting_recipes = {
            # Planks
            ("", "",
             "wood", ""): {"type": "planks", "count": 4},

            # Planks mesa
            ("", "", "",
             "", "", "",
             "wood", "", ""): {"type": "planks", "count": 4},


            # Palos
            ("planks", "", 
             "planks", ""): {"type": "stick", "count": 4},

            # Palos mesa
            ("", "", "",
             "planks", "", "",
             "planks", "", ""): {"type": "stick", "count": 4},

            # Mesa
            ("planks", "planks",
             "planks", "planks"): {"type": "crafting Table", "count": 1}
        }

    def getCraftingGridConfig(self):
        if getattr(self, 'using_3x3', False):
            return {
                'slot_count': 9,
                'columns': 3,
                'start_x': -0.4808201193809509,
                'start_z': 0.59660464525,
                'spacing_x': 0.17395633459091187,
                'spacing_z': 0.18581461906433105,
                'result_x': 0.4210144877433777,
                'result_z': 0.4044528007507324,
                'reverse_z': True,
            }

        return {
            'slot_count': 4,
            'columns': 2,
            'start_x': 0.170,
            'start_z': 0.4,
            'spacing_x': 0.18,
            'spacing_z': 0.157,
            'result_x': 0.740,
            'result_z': 0.470,
            'reverse_z': False,
        }

    def getCraftingSlotPosition(self, slot_index):
        config = self.getCraftingGridConfig()
        col = slot_index % config['columns']
        row = slot_index // config['columns']
        x = config['start_x'] + (col * config['spacing_x'])
        if config['reverse_z']:
            z = config['start_z'] - (row * config['spacing_z'])
        else:
            z = config['start_z'] + (row * config['spacing_z'])
        return x, z

    def checkCraftingClick(self, mx, my, button_name):
        slot_radius = 0.13
        self.using_3x3 = getattr(self, 'using_3x3', False)
        config = self.getCraftingGridConfig()
        result_x = config['result_x']
        result_z = config['result_z']
        print(f"Clickeo en x: {mx}, y: {my}, using_3x3: {self.using_3x3}, button: {button_name}")

        rightClick = (button_name == "mouse3")

        # =========================================================
        # 1. RECOGER EL RESULTADO
        # =========================================================
        if abs(mx - result_x) < slot_radius and abs(my - result_z) < slot_radius:
            if self.craftingResultSlot["type"] != "":
                print("--> [Crafteo] ¡Recogiendo producto de la salida!")
                self.draggedItemData = {"type": self.craftingResultSlot["type"], "count": self.craftingResultSlot["count"]}
                self.draggedItemIndex = ('crafting_result', 0)
                
                if hasattr(self, 'draggedIcon') and self.draggedIcon: self.draggedIcon.destroy()
                self.draggedIcon = OnscreenImage(image=self.itemIcons[self.draggedItemData["type"]], scale=(0.063, 1, 0.063), parent=self.aspect2d)
                self.draggedIcon.setTransparency(TransparencyAttrib.MAlpha)
                self.draggedIcon.setBin('fixed', 30)
                
                self.taskMgr.remove('updateDraggedItemTask')
                self.taskMgr.add(self.updateDraggedItem, 'updateDraggedItemTask')
                
                self.craftingResultSlot = {"type": "", "count": 0}
                active_slots = self.craftingSlots3x3 if self.using_3x3 else self.craftingSlots2x2
                for slot in active_slots:
                    if slot["type"] != "":
                        slot["count"] -= 1
                        if slot["count"] <= 0: slot["type"] = ""; slot["count"] = 0
                
                self.checkCraftingRecipe()
                self.refreshInventoryVisuals()
                return True
            return False

        # =========================================================
        # 2. DETECTAR CLIC EN LOS SLOTS DE LA REJILLA (2x2 o 3x3)
        # =========================================================
        clicked_craft_idx = None

        for i in range(config['slot_count']):
            slot_x, slot_z = self.getCraftingSlotPosition(i)
            if abs(mx - slot_x) < slot_radius and abs(my - slot_z) < slot_radius:
                clicked_craft_idx = i
                break

        # Si no se detectó un slot por el radio, seleccionar el slot más cercano
        if clicked_craft_idx is None:
            best_idx = None
            best_dist = None
            max_allow = slot_radius * 2.0
            for i in range(config['slot_count']):
                slot_x, slot_z = self.getCraftingSlotPosition(i)
                dx = mx - slot_x
                dz = my - slot_z
                dist = (dx*dx + dz*dz) ** 0.5
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_idx = i
            if best_dist is not None and best_dist <= max_allow:
                clicked_craft_idx = best_idx

        if clicked_craft_idx is not None:
            active_slots = self.craftingSlots3x3 if self.using_3x3 else self.craftingSlots2x2
            
            mano_llena = False
            if hasattr(self, 'draggedItemData') and self.draggedItemData is not None:
                if self.draggedItemData.get("type", "") != "":
                    mano_llena = True

            # --- CASO MANO LLENA: DEPOSITAR ---
            if mano_llena:
                if rightClick:
                    if active_slots[clicked_craft_idx]["type"] == "" or active_slots[clicked_craft_idx]["type"] == self.draggedItemData["type"]:
                        if active_slots[clicked_craft_idx]["type"] == "":
                            active_slots[clicked_craft_idx] = {"type": self.draggedItemData["type"], "count": 0}
                        active_slots[clicked_craft_idx]["count"] += 1
                        self.draggedItemData["count"] -= 1
                        if self.draggedItemData["count"] <= 0:
                            self.draggedItemIndex = None; self.draggedItemData = None
                            if hasattr(self, 'draggedIcon') and self.draggedIcon: self.draggedIcon.destroy(); self.draggedIcon = None
                else:
                    if active_slots[clicked_craft_idx]["type"] == self.draggedItemData["type"]:
                        active_slots[clicked_craft_idx]["count"] += self.draggedItemData["count"]
                        self.draggedItemIndex = None; self.draggedItemData = None
                        if hasattr(self, 'draggedIcon') and self.draggedIcon: self.draggedIcon.destroy(); self.draggedIcon = None
                    else:
                        temp_slot = dict(active_slots[clicked_craft_idx])
                        active_slots[clicked_craft_idx] = dict(self.draggedItemData)
                        if temp_slot["type"] != "":
                            self.draggedItemData = temp_slot
                            self.draggedItemIndex = ('crafting', clicked_craft_idx)
                            if hasattr(self, 'draggedIcon') and self.draggedIcon:
                                self.draggedIcon.setImage(self.itemIcons[self.draggedItemData["type"]])
                        else:
                            self.draggedItemIndex = None; self.draggedItemData = None
                            if hasattr(self, 'draggedIcon') and self.draggedIcon: self.draggedIcon.destroy(); self.draggedIcon = None

            # --- CASO MANO VACÍA: RETIRAR ---
            else:
                if active_slots[clicked_craft_idx]["type"] != "":
                    if rightClick and active_slots[clicked_craft_idx]["count"] > 1:
                        take_count = active_slots[clicked_craft_idx]["count"] // 2
                        active_slots[clicked_craft_idx]["count"] -= take_count
                        self.draggedItemData = {"type": active_slots[clicked_craft_idx]["type"], "count": take_count}
                    else:
                        self.draggedItemData = dict(active_slots[clicked_craft_idx])
                        active_slots[clicked_craft_idx] = {"type": "", "count": 0}

                    self.draggedItemIndex = ('crafting_retrieved', clicked_craft_idx)
                    if hasattr(self, 'draggedIcon') and self.draggedIcon: self.draggedIcon.destroy()
                    self.draggedIcon = OnscreenImage(image=self.itemIcons[self.draggedItemData["type"]], scale=(0.063, 1, 0.063), parent=self.aspect2d)
                    self.draggedIcon.setTransparency(TransparencyAttrib.MAlpha)
                    self.draggedIcon.setBin('fixed', 30) 
                    self.taskMgr.remove('updateDraggedItemTask')
                    self.taskMgr.add(self.updateDraggedItem, 'updateDraggedItemTask')

            self.checkCraftingRecipe()
            self.refreshInventoryVisuals()
            return True

        return False

    def checkCraftingRecipe(self):
        self.using_3x3 = getattr(self, 'using_3x3', False)
        if self.using_3x3:
            current_combination = tuple(slot["type"] for slot in self.craftingSlots3x3)
        else:
            current_combination = tuple(slot["type"] for slot in self.craftingSlots2x2)

        if current_combination in self.crafting_recipes:
            recipe_output = self.crafting_recipes[current_combination]
            self.craftingResultSlot = {"type": recipe_output["type"], "count": recipe_output["count"]}
        else:
            self.craftingResultSlot = {"type": "", "count": 0}
        
        self.refreshInventoryVisuals()

    def findNearestInventorySlot(self, mx, my, slot_radius=0.13):
        best_result = None
        best_dist = None

        for slot_index in range(len(self.hotbarItems)):
            slot_x = self.inv_start_x + (slot_index * self.inv_spacing)
            dist = (mx - slot_x) ** 2 + (my - self.inv_z) ** 2
            if dist <= slot_radius ** 2:
                return ('hotbar', slot_index, slot_x, self.inv_z)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_result = ('hotbar', slot_index, slot_x, self.inv_z)

        for i in range(len(self.upperInventoryItems)):
            col = i % 9
            row = i // 9
            slot_x = self.inv_start_x + (col * self.inv_spacing)
            slot_z = self.upper_start_z + (row * self.row_spacing_z)
            dist = (mx - slot_x) ** 2 + (my - slot_z) ** 2
            if dist <= slot_radius ** 2:
                return ('upper', i, slot_x, slot_z)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_result = ('upper', i, slot_x, slot_z)

        if best_result is not None and best_dist is not None and best_dist <= (slot_radius * 1.7) ** 2:
            return best_result

        return None

    def checkInventoryClick(self, button_name):
        if not self.inventoryOpen or not self.mouseWatcherNode.hasMouse():
            return
       
        # 1. Posición del ratón
        mouse_data = self.mouseWatcherNode.getMouse()
        mouse_pos_in_aspect2d = self.aspect2d.getRelativePoint(render2d, Point3(mouse_data.getX(), 0, mouse_data.getY()))
        
        mx = mouse_pos_in_aspect2d.getX()
        my = mouse_pos_in_aspect2d.getZ()
        
        if self.checkCraftingClick(mx, my, button_name):
            return
        

        slot_radius = 0.13
        clicked_hotbar_index = None
        clicked_upper_index = None
        # =========================================================
        # CASO A: NO TENEMOS NADA EN LA MANO -> AGARRAR ÍTEM
        # =========================================================
        if self.draggedItemIndex is None:
            nearest_slot = self.findNearestInventorySlot(mx, my, slot_radius=slot_radius)
            if nearest_slot is not None:
                pool_type, target_idx, _, _ = nearest_slot
                if pool_type == 'hotbar':
                    target_pool = self.hotbarItems
                    target_images = self.itemImagesUI
                    clicked_hotbar_index = target_idx
                else:
                    target_pool = self.upperInventoryItems
                    target_images = self.upperItemImagesUI
                    clicked_upper_index = target_idx
            else:
                target_idx = None
                target_pool = None
                target_images = None
                pool_type = None

            # Procesar el agarre si se encontró una casilla con ítem
            if target_idx is not None and target_pool is not None and target_pool[target_idx]["type"] != "":
                item = target_pool[target_idx]

            if target_idx is not None and target_pool[target_idx]["type"] != "":
                item = target_pool[target_idx]
                
                # --- LÓGICA DE CLICK DERECHO (AGARRAR LA MITAD) ---
                if button_name == "mouse3" and item["count"] > 1:
                    take_count = item["count"] // 2
                    item["count"] -= take_count
                    # Creamos el ítem arrastrado con la mitad
                    self.draggedItemData = {"type": item["type"], "count": take_count}
                    # Mantenemos el ítem original en la casilla (no ocultar la imagen del slot)
                else:
                    # Click izquierdo: agarra todo
                    self.draggedItemData = {"type": item["type"], "count": item["count"]}
                    target_pool[target_idx] = {"type": "", "count": 0}
                    if isinstance(target_images, list) and 0 <= target_idx < len(target_images) and target_images[target_idx]:
                        target_images[target_idx].hide()

                self.draggedItemIndex = (pool_type, target_idx)
                
                # Crear icono flotante
                self.draggedIcon = OnscreenImage(
                    image=self.itemIcons[self.draggedItemData["type"]],
                    scale=(0.063, 1, 0.063),
                    parent=self.aspect2d
                )
                self.draggedIcon.setTransparency(TransparencyAttrib.MAlpha)
                self.draggedIcon.setBin('fixed', 30) 
                self.taskMgr.add(self.updateDraggedItem, 'updateDraggedItemTask')
                return

        # =========================================================
        # CASO B: YA TENEMOS UN ÍTEM EN LA MANO -> SOLTAR O INTERCAMBIAR
        # =========================================================
        else:
            nearest_slot = self.findNearestInventorySlot(mx, my, slot_radius=slot_radius)
            if nearest_slot is not None:
                pool_type, target_idx, _, _ = nearest_slot
                if pool_type == 'hotbar':
                    clicked_hotbar_index = target_idx
                else:
                    clicked_upper_index = target_idx

            origin_type, origin_idx = self.draggedItemIndex
            
            if origin_type == 'hotbar':
                origin_items = self.hotbarItems
                origin_images = self.itemImagesUI
            elif origin_type == 'upper':
                origin_items = self.upperInventoryItems
                origin_images = self.upperItemImagesUI
            elif origin_type in ('crafting', 'crafting_retrieved'):
                # Origen desde la rejilla de crafteo (2x2 o 3x3)
                origin_items = self.craftingSlots3x3 if getattr(self, 'using_3x3', False) else self.craftingSlots2x2
                origin_images = getattr(self, 'craftingImagesUI', [])
            elif origin_type == 'crafting_result':
                origin_items = [self.craftingResultSlot]
                origin_images = [getattr(self, 'craftingResultImageUI', None)]
            else:
                origin_items = [{"type": "", "count": 0}]
                origin_images = [None]

            if clicked_hotbar_index is not None:
                dest_items = self.hotbarItems
                dest_images = self.itemImagesUI
                dest_idx = clicked_hotbar_index
            elif clicked_upper_index is not None:
                dest_items = self.upperInventoryItems
                dest_images = self.upperItemImagesUI
                dest_idx = clicked_upper_index
            else:
                # Si no hay destino válido, devolvemos el ítem a su origen si es posible
                if isinstance(origin_images, list) and 0 <= origin_idx < len(origin_images):
                    if origin_images[origin_idx]:
                        origin_images[origin_idx].show()
                elif origin_images is not None and hasattr(origin_images, 'show'):
                    try:
                        origin_images.show()
                    except Exception:
                        pass

                if hasattr(self, 'cleanDraggedItem'):
                    self.cleanDraggedItem()
                return

            dest_item = dest_items[dest_idx]

            # --- LÓGICA DE SOLTAR CON CLICK DERECHO (DEPOSITAR 1 ÍTEM) ---
            if button_name == "mouse3":
                # Si la casilla está vacía o tiene el mismo tipo de ítem
                if dest_item["type"] == "" or dest_item["type"] == self.draggedItemData["type"]:
                    if dest_item["type"] == "":
                        dest_items[dest_idx] = {"type": self.draggedItemData["type"], "count": 0}
                    
                    dest_items[dest_idx]["count"] += 1
                    self.draggedItemData["count"] -= 1
                    
                    # Actualizar gráfico del destino
                    self.refreshInventoryVisuals()

                    # Si nos quedamos sin ítems en la mano, limpiamos el arrastre
                    if self.draggedItemData["count"] <= 0:
                        if hasattr(self, 'cleanDraggedItem'): self.cleanDraggedItem()
                    return
            
            # --- LÓGICA DE CLICK IZQUIERDO---
            else:
                if dest_item["type"] == self.draggedItemData["type"]:
                    # Mismo tipo: se fusionan las cantidades
                    dest_item["count"] += self.draggedItemData["count"]
                    if hasattr(self, 'cleanDraggedItem'): self.cleanDraggedItem()
                else:
                    # Tipo diferente: intercambio clásico de Minecraft
                    dest_items[dest_idx] = self.draggedItemData
                    # El ítem que estaba en el destino pasa a ser el arrastrado
                    if dest_item["type"] != "":
                        self.draggedItemData = dest_item
                        # Actualizar la imagen flotante aquí si es necesario
                    else:
                        if hasattr(self, 'cleanDraggedItem'): self.cleanDraggedItem()
                
                self.refreshInventoryVisuals()

    def updateDraggedItem(self, task):
        if self.draggedIcon and self.mouseWatcherNode.hasMouse():
            
            mouseData = self.mouseWatcherNode.getMouse()
            mousePosInAspect2d = aspect2d.getRelativePoint(render2d, Point3(mouseData.getX(), 0, mouseData.getY()))
            
            
            self.draggedIcon.setPos(mousePosInAspect2d.getX(), 0, mousePosInAspect2d.getZ())
        return task.cont

    def selectSlotByKeyboard(self, slotIndex):
        # Si el inventario está abierto, no dejamos cambiar de bloque con los números
        if getattr(self, 'inventoryOpen', False):
            return

        # Movemos el selector visual en la barra de juego
        gameStartX = getattr(self, 'ui_start_x', -0.5241)
        gameSpacing = getattr(self, 'ui_slot_spacing', 0.131)
        newXPos = gameStartX + (slotIndex * gameSpacing)
        
        if hasattr(self, 'selector_ui') and self.selector_ui:
            self.selector_ui.setX(newXPos)

        # --- SELECCIÓN DINÁMICA DE BLOQUE ---
        if 0 <= slotIndex < len(self.hotbarItems):
            chosenBlock = self.hotbarItems[slotIndex]
            
            # Guardamos el bloque en tu variable exacta
            self.selectedBlockType = chosenBlock
            
            # Si tienes el texto en pantalla, actualizamos el nombre del bloque
            if hasattr(self, 'blockText') and self.blockText:
                self.blockText.setText(chosenBlock.capitalize())

    def cleanDraggedItem(self):
        if hasattr(self, 'draggedIcon') and self.draggedIcon:
            self.draggedIcon.destroy()
        self.draggedIcon = None
        self.draggedItemIndex = None
        if self.taskMgr.hasTaskNamed('updateDraggedItemTask'):
            self.taskMgr.remove('updateDraggedItemTask')

    def handleLeftClick(self):
        if self.inventoryOpen:
            self.checkInventoryClick("mouse1")
        else:
            self.removeBlock()
            self.captureMouse()
   
    def dropItem(self, x, y, z, itemType):
        itemNode = self.render.attachNewNode("dropped-item")
        itemNode.setPos(x, y, z + 0.6)
        itemNode.setScale(0.2)         
        itemNode.setName(itemType)

        
        # Copiamos el modelo correspondiente según el tipo de ítem
        if itemType == 'grass': self.grassBlock.copyTo(itemNode)
        elif itemType == 'dirt': self.dirtBlock.copyTo(itemNode)
        elif itemType == 'sand': self.sandBlock.copyTo(itemNode)
        elif itemType == 'stone': self.stoneBlock.copyTo(itemNode)
        elif itemType == 'wood': self.woodLog.copyTo(itemNode)
        elif itemType == 'planks': self.woodPlanks.copyTo(itemNode)
        elif itemType == 'leaves': self.leavesBlock.copyTo(itemNode)
        elif itemType == 'glass': self.glassBlock.copyTo(itemNode)
        elif itemType == 'cobblestone': self.cobbleBlock.copyTo(itemNode)
        elif itemType == 'crafting Table': self.craftingTable.copyTo(itemNode)
        elif itemType == 'poppy': self.poppyItem.copyTo(itemNode)

        self.droppedItems.append({
            "node": itemNode,
            "type": itemType,
            "base_z": z + 0.6,
            "time": 0.0
        })
        self.type = itemType

    def updateDroppedItems(self, task): 
        dt = self.globalClock.getDt()
        playerPos = self.camera.getPos()
        inventory_changed = False
    
        # Iteramos la lista al revés de forma segura
        for i in range(len(self.droppedItems) - 1, -1, -1):
            item = self.droppedItems[i]
            node = item["node"]
        
            # Validar si el nodo sigue existiendo en Panda3D
            if not node or node.isEmpty():
                self.droppedItems.pop(i)
                continue 

            # RECOLECCIÓN: Calcular distancia
            itemPos = node.getPos()
            distance = (playerPos - itemPos).length()
        
            if distance < 2.2: 
                added = False
                item_type = item["type"]
            
                # 1. Buscar si ya existe el ítem en la HOTBAR para agruparlo
                for slot in self.hotbarItems:
                    if slot["type"] == item_type and slot["count"] < 64:
                        slot["count"] += 1
                        added = True
                        break
            
                # 2. Si no, buscar si ya existe en el INVENTARIO SUPERIOR
                if not added:
                    for slot in self.upperInventoryItems:
                        if slot["type"] == item_type and slot["count"] < 64:
                            slot["count"] += 1
                            added = True
                            break
            
                # 3. Si no teníamos ese bloque, buscamos un HUECO VACÍO en la hotbar
                if not added:
                    for slot in self.hotbarItems:
                        if slot["type"] == "":
                            slot["type"] = item_type
                            slot["count"] = 1
                            added = True
                            break
                        
                # 4. Si la hotbar está llena, buscamos un HUECO VACÍO arriba
                if not added:
                    for slot in self.upperInventoryItems:
                        if slot["type"] == "":
                            slot["type"] = item_type
                            slot["count"] = 1
                            added = True
                            break
            
                if added:
                    node.removeNode()
                    self.droppedItems.pop(i)
                    inventory_changed = True
                    continue

            # ANIMACIÓN 
            node.setH(node.getH() + 60.0 * dt)
            item["time"] += dt
            from math import sin 
            bobbing = sin(item["time"] * 3.0) * 0.15
            node.setZ(item["base_z"] + bobbing)

        if inventory_changed:
            self.refreshInventoryVisuals()

        return task.cont

    def refreshInventoryVisuals(self):
        
        is_using_3x3 = getattr(self, 'using_3x3', False)
        inventoryOpen = getattr(self, 'inventoryOpen', False)

        if hasattr(self, 'craftingTableBg') and self.craftingTableBg:
            # Mostrar/ocultar el fondo de crafteo según el estado real del inventario
            if inventoryOpen and getattr(self, 'using_3x3', False):
                self.craftingTableBg.show()
            else:
                self.craftingTableBg.hide()
        
        # Variables de posicionamiento base originales de la Hotbar (abajo)
        game_start_x = getattr(self, 'ui_start_x', -0.5241)
        game_spacing = getattr(self, 'ui_slot_spacing', 0.131)
        
        # Variables de posicionamiento del Inventario Superior (arriba)
        inv_start_x = getattr(self, 'inv_start_x', -0.725)
        inv_spacing = getattr(self, 'inv_spacing', 0.18)
        inv_z = getattr(self, 'inv_z', -0.663)

        # Inicializar las listas de textos sólo si no existen todavía en la clase
        if not hasattr(self, 'itemImagesUI') or len(self.itemImagesUI) != 9:
            self.itemImagesUI = [None] * 9

        if not hasattr(self, 'upperItemImagesUI') or len(self.upperItemImagesUI) != len(self.upperInventoryItems):
            self.upperItemImagesUI = [None] * len(self.upperInventoryItems)


        # =========================================================
        # 1. ACTUALIZAR IMÁGENES Y TEXTOS DE LA HOTBAR
        # =========================================================
        for i in range(9):
            item = self.hotbarItems[i]
            
            # Limpiar texto anterior de forma segura antes de evaluar
            if self.hotbarTextsUI[i]:
                self.hotbarTextsUI[i].destroy()
                self.hotbarTextsUI[i] = None
                
            if item["type"] != "":
                
                if getattr(self, 'inventoryOpen', False):
                    
                    x = self.inv_start_x + (i * self.inv_spacing)
                    z = self.inv_z 
                    escala = (0.063, 1, 0.063) 
                else:
                    
                    x = self.ui_start_x + (i * self.ui_slot_spacing)
                    z = -0.85
                    escala = (0.045, 1, 0.045) 

                if self.itemImagesUI[i]:
                    self.itemImagesUI[i].setImage(self.itemIcons[item["type"]])
                    self.itemImagesUI[i].setPos(x, 0, z) 
                    self.itemImagesUI[i].setScale(escala) 
                    self.itemImagesUI[i].setTransparency(TransparencyAttrib.MAlpha)
                    self.itemImagesUI[i].show()
                else:
                    icon = OnscreenImage(
                        image=self.itemIcons[item["type"]],
                        pos=(x, 0, z),
                        scale=escala,
                        parent=self.aspect2d
                    )
                    icon.setTransparency(TransparencyAttrib.MAlpha)
                    self.itemImagesUI[i] = icon
                
                # Renderizar la cantidad si es mayor a 1
                if item["count"] > 1 and self.itemImagesUI[i]:
                    # Calculamos la posición exacta usando las variables matemáticas directas, no el getPos()
                    if getattr(self, 'inventoryOpen', False):
                        text_x = self.inv_start_x + (i * self.inv_spacing) + 0.035
                        text_z = self.inv_z - 0.035
                        text_scale = 0.045
                    else:
                        text_x = self.ui_start_x + (i * self.ui_slot_spacing) + 0.025
                        text_z = -0.85 - 0.025
                        text_scale = 0.035
                    
                    self.hotbarTextsUI[i] = OnscreenText(
                        text=str(item["count"]),
                        pos=(text_x, text_z),
                        scale=text_scale,
                        fg=(1, 1, 1, 1),
                        shadow=(0, 0, 0, 1),
                        parent=self.aspect2d
                    )
            else:
                # Si la casilla está vacía, ocultamos la imagen
                if self.itemImagesUI[i]:
                    self.itemImagesUI[i].hide()

        # =========================================================
        # 2. ACTUALIZAR IMÁGENES Y TEXTOS DEL INVENTARIO SUPERIOR
        # =========================================================
        for i in range(len(self.upperInventoryItems)):
            item = self.upperInventoryItems[i]
            
            # Limpiar texto anterior de forma segura antes de evaluar
            if self.upperInventoryTextsUI[i]:
                self.upperInventoryTextsUI[i].destroy()
                self.upperInventoryTextsUI[i] = None
                
            # Solo manejamos las imágenes si el inventario está abierto
            if getattr(self, 'inventoryOpen', False):
                if item["type"] != "":
                    # Lógica para actualizar la imagen superior
                    if self.upperItemImagesUI[i]:
                        self.upperItemImagesUI[i].setImage(self.itemIcons[item["type"]])
                        self.upperItemImagesUI[i].setTransparency(TransparencyAttrib.MAlpha)
                        self.upperItemImagesUI[i].show()
                    else:
                        col = i % 9
                        row = i // 9
                        slot_x = self.inv_start_x + (col * self.inv_spacing)
                        slot_z = self.upper_start_z + (row * self.row_spacing_z)
                        
                        icon = OnscreenImage(
                            image=self.itemIcons[item["type"]],
                            pos=(slot_x, 0, slot_z),
                            scale=(0.063, 1, 0.063),
                            parent=self.aspect2d
                        )
                        icon.setTransparency(TransparencyAttrib.MAlpha)
                        self.upperItemImagesUI[i] = icon

                    # Renderizar cantidad en inventario superior
                    if item["count"] > 1 and self.upperItemImagesUI[i]:
                        # Calculamos la posición exacta usando filas y columnas matemáticas directas
                        col = i % 9
                        row = i // 9
                        text_x = self.inv_start_x + (col * self.inv_spacing) + 0.035
                        text_z = self.upper_start_z + (row * self.row_spacing_z) - 0.035
                        
                        self.upperInventoryTextsUI[i] = OnscreenText(
                            text=str(item["count"]),
                            pos=(text_x, text_z),
                            scale=0.045, 
                            fg=(1, 1, 1, 1),
                            shadow=(0, 0, 0, 1),
                            parent=self.aspect2d
                        )
                else:
                    # Si el ítem se vació
                    if self.upperItemImagesUI[i]:
                        self.upperItemImagesUI[i].hide()
            else:
                # Si el inventario se cerró, nos aseguramos de ocultar los iconos superiores
                if self.upperItemImagesUI[i]:
                    self.upperItemImagesUI[i].hide()

        # =========================================================
        # ESCUDO DE SEGURIDAD PARA PASAR EL ATTRIBUTEERROR
        # =========================================================
        if not hasattr(self, 'craftingSlots2x2'):
            self.craftingSlots2x2 = [{"type": "", "count": 0} for _ in range(4)]
        if not hasattr(self, 'craftingResultSlot'):
            self.craftingResultSlot = {"type": "", "count": 0}

        # =========================================================
        # 3. RENDERIZAR REJILLA DE CRAFTEO 
        # =========================================================
        slot_count = 9 if is_using_3x3 else 4
        if not hasattr(self, 'craftingImagesUI') or len(self.craftingImagesUI) != slot_count:
            self.craftingImagesUI = [None] * slot_count
        if not hasattr(self, 'craftingTextsUI') or len(self.craftingTextsUI) != slot_count:
            self.craftingTextsUI = [None] * slot_count

        active_slots = self.craftingSlots3x3 if is_using_3x3 else self.craftingSlots2x2

        for i in range(slot_count):
            if i >= len(self.craftingImagesUI):
                break
            item = active_slots[i]

            if self.craftingTextsUI[i]:
                self.craftingTextsUI[i].destroy()
                self.craftingTextsUI[i] = None

            if getattr(self, 'inventoryOpen', False) and item["type"] != "":
                x, z = self.getCraftingSlotPosition(i)

                if self.craftingImagesUI[i]:
                    self.craftingImagesUI[i].setImage(self.itemIcons[item["type"]])
                    self.craftingImagesUI[i].setPos(x, 0, z)
                    self.craftingImagesUI[i].setTransparency(TransparencyAttrib.MAlpha)
                    self.craftingImagesUI[i].setBin('fixed', 25)
                    self.craftingImagesUI[i].show()
                else:
                    self.craftingImagesUI[i] = OnscreenImage(
                        image=self.itemIcons[item["type"]],
                        pos=(x, 0, z),
                        scale=(0.063, 1, 0.063),
                        parent=self.aspect2d
                    )
                    self.craftingImagesUI[i].setTransparency(TransparencyAttrib.MAlpha)
                    self.craftingImagesUI[i].setBin('fixed', 25)
                    # Asegurar que la imagen esté visible y registrar su creación
                    try:
                        self.craftingImagesUI[i].show()
                    except Exception:
                        pass
                if item["count"] > 1:
                    self.craftingTextsUI[i] = OnscreenText(
                        text=str(item["count"]),
                        pos=(x + 0.035, z - 0.035),
                        scale=0.045,
                        fg=(1, 1, 1, 1),
                        shadow=(0, 0, 0, 1),
                        parent=self.aspect2d
                    )
                    self.craftingTextsUI[i].setBin('fixed', 26)
            else:
                if self.craftingImagesUI[i]:
                    self.craftingImagesUI[i].hide()

        if not inventoryOpen:
            for i in range(len(self.craftingImagesUI)):
                if self.craftingImagesUI[i]:
                    self.craftingImagesUI[i].hide()

        # =========================================================
        # 4. RENDERIZAR CASILLA DE RESULTADO DEL CRAFTEO
        # =========================================================
        config = self.getCraftingGridConfig()
        result_x = config['result_x']
        result_z = config['result_z']

        if hasattr(self, 'craftingResultTextUI') and self.craftingResultTextUI:
            self.craftingResultTextUI.destroy()
            self.craftingResultTextUI = None

        if getattr(self, 'inventoryOpen', False) and self.craftingResultSlot["type"] != "":
            print(f"--> [Render Crafteo] Dibujando RESULTADO: {self.craftingResultSlot['type']} en X={result_x:.3f}, Z={result_z:.3f}")

            if not hasattr(self, 'craftingResultImageUI') or not self.craftingResultImageUI:
                self.craftingResultImageUI = OnscreenImage(
                    image=self.itemIcons[self.craftingResultSlot["type"]],
                    pos=(result_x, 0, result_z),
                    scale=(0.063, 1, 0.063),
                    parent=self.aspect2d
                )
                self.craftingResultImageUI.setTransparency(TransparencyAttrib.MAlpha)
                self.craftingResultImageUI.setBin('fixed', 25) 
            else:
                self.craftingResultImageUI.setTransparency(TransparencyAttrib.MAlpha)
                self.craftingResultImageUI.setImage(self.itemIcons[self.craftingResultSlot["type"]])
                self.craftingResultImageUI.setBin('fixed', 25)
                self.craftingResultImageUI.show()

            if self.craftingResultSlot["count"] > 1:
                self.craftingResultTextUI = OnscreenText(
                    text=str(self.craftingResultSlot["count"]),
                    pos=(result_x + 0.035, result_z - 0.035),
                    scale=0.045,
                    fg=(1, 1, 1, 1),
                    shadow=(0, 0, 0, 1),
                    parent=self.aspect2d
                )
                self.craftingResultTextUI.setBin('fixed', 26)
        else:
            if hasattr(self, 'craftingResultImageUI') and self.craftingResultImageUI:
                self.craftingResultImageUI.hide()

        # Refrescar mano activa
        current_slot = getattr(self, 'selected_slot', getattr(self, 'selectedSlot', 0))
        if 0 <= current_slot < 9 and self.hotbarItems[current_slot]["type"] != "":
            self.changeItem(self.hotbarItems[current_slot]["type"], current_slot)

    def setupHotbarUI(self):
        self.hotbarBg = OnscreenImage(image='Hotbar.png',
                                      pos= (0, 0, -0.85),
                                      scale=(0.6, 1, 0.08))
        self.hotbarBg.setTransparency(TransparencyAttrib.MAlpha)
        self.selector_ui = OnscreenImage(image='Hotbar_selector.png',
                                         pos=(-0.5241, 0, -0.85),
                                         scale=(0.08, 1, 0.08))
        self.selector_ui.setTransparency(TransparencyAttrib.MAlpha)

        self.hotbarItems = [{"type": "", "count": 0} for _ in range(9)]
        self.itemIcons = {
            'grass': 'grass.png',
            'dirt': 'dirt.png',
            'sand': 'sand.png',
            'stone': 'stone.png',
            'wood': 'wood.png',
            'planks': 'planks.png',
            'leaves': 'leaves.png',
            'glass': 'glass.png',
            'cobblestone': 'cobblestone.png',
            'stick': 'stick.png',
            'crafting Table': 'crafting.png',
            'poppy': 'poppy.png'
        }
        # Cambiamos a lista vacía
        self.itemImagesUI = []

        for slot_index, item_name in enumerate(self.hotbarItems):
            # Comprobamos si el tipo de ítem dentro del diccionario no está vacío
            if item_name["type"] != "":
                x = -0.5241 + (slot_index * 0.131)

                # Sacamos la imagen del diccionario
                imagen_ruta = self.itemIcons[item_name["type"]]

                icon = OnscreenImage(
                    image=imagen_ruta,
                    pos=(x, 0, -0.85), 
                    scale=(0.045, 1, 0.045) 
                )
                icon.setTransparency(TransparencyAttrib.MAlpha)
                self.itemImagesUI.append(icon)
            else:
                # Si el slot está vacío, añadimos None para mantener el orden de los 9 espacios
                self.itemImagesUI.append(None)
        
    def selectSlot(self, slotIndex):
        newXPos = -0.5241 + (slotIndex * 0.133)
        self.selector_ui.setX(newXPos)
        self.current_block_type = self.hotbarSlots[slotIndex]

    def removeBlock(self):
        if self.rayQueue.getNumEntries() > 0:
            self.rayQueue.sortEntries()
            firstEntry = self.rayQueue.getEntry(0)
            
            hitNodePath = firstEntry.getIntoNodePath()
            blockOwner = hitNodePath.getPythonTag('owner')
            
            if blockOwner:
                
                distanceFromPlayer = blockOwner.getDistance(self.camera)
                if distanceFromPlayer < 10: # Rango de 4.5 bloques
                    
                    x, y, z = blockOwner.getPos()
                    blockType = blockOwner.getName()
                
                    realX = int(round(x) // 2)
                    realY = int(round(y) // 2)
                    realZ = int(round(z) // 2)

                    cx = realX // 16
                    cy = realY // 16
                    localX = realX % 16
                    localY = realY % 16

                    # Borrar el bloque de la estructura de datos del chunk
                    if (cx, cy) in self.chunksData:
                        if (localX, localY, realZ) in self.chunksData[(cx, cy)]:
                            del self.chunksData[(cx, cy)][(localX, localY, realZ)]

                    aboveZ = realZ + 1
                    aboveCx = cx
                    aboveCy = cy
                    aboveLocalX = localX
                    aboveLocalY = localY
 
                    if (aboveCx, aboveCy) in self.chunksData:
                        if (aboveLocalX, aboveLocalY, aboveZ) in self.chunksData[(aboveCx, aboveCy)]:
                            blockAboveType = self.chunksData[(aboveCx, aboveCy)][(aboveLocalX, aboveLocalY, aboveZ)]
                            if blockAboveType in ['poppy',]:
                                # Soltamos el ítem correspondiente
                                if blockAboveType in self.itemIcons:
                                    self.dropItem(x, y, z + 2, blockAboveType)
                                    
                                # Lo eliminamos por completo de los datos lógicos
                                del self.chunksData[(aboveCx, aboveCy)][(aboveLocalX, aboveLocalY, aboveZ)]

                    # Soltar item
                    if blockType in self.itemIcons:
                        self.dropItem(x, y, z, blockType)

                    # Borramos el bloque
                    blockOwner.removeNode()
                    hitNodePath.removeNode()
                    self.rayQueue.clearEntries()
                    
                    # Refrescar el chunk
                    self.rebuildChunkVisuals(cx, cy)

    def placeBlock(self):
        slotIndex = self.selectedSlot if hasattr(self, 'selectedSlot') else getattr(self, 'selected_slot', 0)
        currentSlot = self.hotbarItems[slotIndex]
        self.current_slot = currentSlot
        
        if currentSlot["type"] == "" or currentSlot["count"] <= 0:
            return

        self.cTrav.traverse(self.render)

        if self.rayQueue.getNumEntries() > 0:
            self.rayQueue.sortEntries()
            rayHit = self.rayQueue.getEntry(0)
        
            hitCollider = rayHit.getIntoNodePath()
            normal = rayHit.getSurfaceNormal(self.render) 
            hitObject = hitCollider.getPythonTag('owner')

            if hitObject:
                distanceFromPlayer = hitObject.getDistance(self.camera)
                if distanceFromPlayer < 10:
                    hitBlockPos = hitObject.getPos()
                    newBlockPos = hitBlockPos + normal * 2 
            
                    blockType = currentSlot["type"]

                    realX = int(round(newBlockPos.x) // 2)
                    realY = int(round(newBlockPos.y) // 2)
                    realZ = int(round(newBlockPos.z) // 2)
                    
                    cx = realX // 16
                    cy = realY // 16
                    localX = realX % 16
                    localY = realY % 16

                    if (cx, cy) not in self.chunksData:
                        self.chunksData[(cx, cy)] = {}
                    self.chunksData[(cx, cy)][(localX, localY, realZ)] = blockType

                    currentSlot["count"] -= 1
                    if currentSlot["count"] <= 0:
                        currentSlot["type"] = ""
                        currentSlot["count"] = 0
                        self.changeItem("", slotIndex)

                    self.refreshInventoryVisuals()

                    if (cx, cy) in self.chunksData:
                        if (localX, localY, realZ) in self.chunksData[(cx, cy)]:
                            currentBlockAtPos = self.chunksData[(cx, cy)][(localX, localY, realZ)]
                            if currentBlockAtPos in ['poppy',]:
                                self.dropItem(localX, localY, realZ + 2, currentBlockAtPos)
                                del self.chunksData[(cx, cy)][(localX, localY, realZ)]

                    # Refrescamos instantáneamente el Chunk afectado inyectando el nuevo bloque y su colisión
                    self.rebuildChunkVisuals(cx, cy)

    def rebuildChunkVisuals(self, cx, cy):
        
        # Buscamos en todo el juego si ya existía un nodo con el nombre de este chunk y lo borramos
        oldNodes = self.render.findAllMatches(f"**/Visual_Chunk_{cx}_{cy}")
        for oldNode in oldNodes:
            if not oldNode.isEmpty():
                oldNode.removeNode()

        if (cx, cy) in self.activeVisualChunks:
            if self.activeVisualChunks[(cx, cy)] and not self.activeVisualChunks[(cx, cy)].isEmpty():
                self.activeVisualChunks[(cx, cy)].removeNode()
            del self.activeVisualChunks[(cx, cy)]

        # Creamos el nuevo contenedor raíz exclusivo para ESTE chunk
        chunkNode = self.render.attachNewNode(f"Visual_Chunk_{cx}_{cy}")
        blocks = self.chunksData.get((cx, cy), {})

        for (x, y, z), blockType in blocks.items():
            neighborCheckers = [
                (x, y, z + 1),     
                (x + 1, y, z),     
                (x - 1, y, z),     
                (x, y + 1, z),     
                (x, y - 1, z)      
            ]
            
            isBlockHidden = True
            for nx, ny, nz in neighborCheckers:
                neighborType = blocks.get((nx, ny, nz))
                if neighborType is None or neighborType in ['leaves', 'glass', 'poppy']:
                    isBlockHidden = False
                    break
            
            if isBlockHidden:
                continue

            realX = ((cx * 16) + x) * 2
            realY = ((cy * 16) + y) * 2
            realZ = z * 2
            
            # Conectamos el bloque visual dentro del nodo del Chunk
            self.createNewBlock(realX, realY, realZ, blockType, parentNode=chunkNode)


            if blockType in ['poppy',]:
                continue

            # Conectamos el colisionador físico dentro de este mismo chunkNode
            blockSolid = CollisionBox((realX, realY, realZ), 1, 1, 1)
            blockNode = CollisionNode('block-collision-node')
            blockNode.addSolid(blockSolid)
            blockNode.setIntoCollideMask(BitMask32.bit(1) | BitMask32.bit(2)) 
            collider = chunkNode.attachNewNode(blockNode)
            
            tempNode = chunkNode.attachNewNode('temp-placeholder')
            tempNode.setPos(realX, realY, realZ)
            tempNode.setName(blockType)
            collider.setPythonTag('owner', tempNode)

        self.activeVisualChunks[(cx, cy)] = chunkNode

    def updateKeyMap(self, key, value):

        if self.cameraSwingFactor:
            self.keyMap[key] = value
        else:
            self.keyMap[key] = False

    def setupControls(self):
        self.keyMap = {
            "forward": False,
            "backward": False,
            "left": False,
            "right": False,
            "up": False,
            "down": False,
        }

        self.accept('escape', self.releaseMouse)
        self.accept('mouse1', self.handleLeftClick)
        self.accept('mouse3', self.handleRightClick)
        self.acceptOnce('e', self.setupInventoryUI)

        self.accept('w', self.updateKeyMap, ['forward', True])
        self.accept('w-up', self.updateKeyMap, ['forward', False])
        self.accept('a', self.updateKeyMap, ['left', True])
        self.accept('a-up', self.updateKeyMap, ['left', False])
        self.accept('s', self.updateKeyMap, ['backward', True])
        self.accept('s-up', self.updateKeyMap, ['backward', False])
        self.accept('d', self.updateKeyMap, ['right', True])
        self.accept('d-up', self.updateKeyMap, ['right', False])
        self.accept('space', self.doJump)
        

        self.accept('1', self.changeItem, ['grass', 0])
        self.accept('2', self.changeItem, ['dirt', 1])
        self.accept('3', self.changeItem, ['sand', 2])
        self.accept('4', self.changeItem, ['stone', 3])
        self.accept('5', self.changeItem, ['wood', 4])
        self.accept('6', self.changeItem, ['planks', 5])
        self.accept('7', self.changeItem, ['leaves', 6])
        self.accept('8', self.changeItem, ['glass', 7])
        self.accept('9', self.changeItem, ['cobblestone', 8])

    def handleRightClick(self):
        if self.inventoryOpen:
            self.checkInventoryClick("mouse3")
        else:
            # === DETECTOR DE MESA DE CRAFTEO MEDIANTE EL NOMBRE DEL NODO ===
            if self.rayQueue.getNumEntries() > 0:
                self.rayQueue.sortEntries()
                firstEntry = self.rayQueue.getEntry(0)
                hitNodePath = firstEntry.getIntoNodePath()
                blockOwner = hitNodePath.getPythonTag('owner')
                
                if blockOwner:
                    # Obtenemos el nombre exacto del bloque
                    nombre_bloque = blockOwner.getName()
                    
                    
                    if "crafting" in nombre_bloque.lower():
                        
                        # 1. Encendemos la mesa grande
                        self.using_3x3 = True
                        self.inventoryOpen = False
                        
                        # 2. Desplegamos la interfaz de crafting
                        self.setupInventoryUI()
                        
                        return # Cortamos para que no coloque un bloque encima
            
            # Si no era una mesa o la mirilla estaba al aire, colocamos un cubo normal
            self.placeBlock()   

    def changeItem(self, blockID, slotIndex):
        # 1. Bloqueamos el cambio de ítem si el inventario grande está abierto
        if getattr(self, 'inventoryOpen', False):
            return

        # 2. Guardamos la casilla seleccionada en tu variable actual
        self.selected_slot = slotIndex 

        # 
        if 0 <= slotIndex < len(self.hotbarItems):
            chosenBlock = self.hotbarItems[slotIndex]["type"]
            self.setSelectedBlockType(chosenBlock)
            
            
            # Si tienes el texto de la pantalla, actualizamos el nombre del bloque
            if hasattr(self, 'blockText') and self.blockText:
                self.blockText.setText(chosenBlock.capitalize())

        # 4. Movemos el selector visual por la Hotbar usando tus medidas exactas (0.133)
        newXpos = -0.53 + (slotIndex * 0.133)
        if hasattr(self, 'selector_ui') and self.selector_ui:
            self.selector_ui.setX(newXpos)   
        
        # 5. Actualizamos el bloque que se ve en la mano del personaje
        self.updateHandBlock()   

    def captureMouse(self):
        self.cameraSwingActivated = True
        md = self.win.getPointer(0)
        self.lastMouseX = md.getX()
        self.lastMouseY = md.getY()

        properties = WindowProperties()
        properties.setCursorHidden(True)
        properties.setMouseMode(WindowProperties.M_relative)
        self.win.requestProperties(properties)

    def releaseMouse(self):
        self.cameraSwingActivated = False
        properties = WindowProperties()
        properties.setCursorHidden(False)
        properties.setMouseMode(WindowProperties.M_absolute)
        self.win.requestProperties(properties)

    def setupFog(self):
        from panda3d.core import Fog
        
        self.gameFog = Fog("SkyFog")
        
        fogColor = (0.47, 0.65, 1.0) 
        self.gameFog.setColor(*fogColor)
       
        self.gameFog.setLinearRange(32.0, 70.0)
        

        self.render.setFog(self.gameFog)

    def setupCamera(self):
        self.disableMouse()
        self.camLens.setFov(80)
        self.camLens.setNear(0.1)
        self.camLens.setFar(100)
        

        self.crosshairs = OnscreenImage(
            image = 'crosshairs.png',
            pos = (0, 0, 0),
            scale = 0.05,
        )
        self.crosshairs.setTransparency(TransparencyAttrib.MAlpha)

       
        radius = 0.9
        bottom_z = -3.24 + radius        
        top_z = (-3.24 + 3.8) - radius   
        
        playerCapsule = CollisionCapsule(0, 0, bottom_z, 0, 0, top_z, radius)
        
        playerNode = CollisionNode('player-collider')
        playerNode.addSolid(playerCapsule)
        playerNode.setFromCollideMask(BitMask32.bit(1))
        playerNode.setIntoCollideMask(0)
        playerNodePath = self.camera.attachNewNode(playerNode)
        self.playerNodePath = playerNodePath
        self.pusher = CollisionHandlerPusher()
        self.pusher.addCollider(playerNodePath, self.camera)

        self.cTrav = CollisionTraverser()
        self.cTrav.addCollider(playerNodePath, self.pusher)
        
        ray = CollisionRay()
        ray.setFromLens(self.camNode, (0, 0))
        rayNode = CollisionNode('line-of-sight')
        rayNode.addSolid(ray)
        rayNode.setFromCollideMask(BitMask32.bit(2)) 
        rayNode.setIntoCollideMask(0)
        
        rayNodePath = self.camera.attachNewNode(rayNode)
        self.rayQueue = CollisionHandlerQueue()
        self.cTrav.addCollider(rayNodePath, self.rayQueue)

    def createNewBlock(self, x, y, z, type, parentNode):
        self.newBlockNode = parentNode.attachNewNode('new-block-placeholder')
        self.newBlockNode.setPos(x, y, z)
        self.newBlockNode.setName(type)

        if type == 'grass':
            self.grassBlock.instanceTo(self.newBlockNode)
        elif type == 'dirt':
            self.dirtBlock.instanceTo(self.newBlockNode)
        elif type == 'sand':
            self.sandBlock.instanceTo(self.newBlockNode)
        elif type == 'stone':
            self.stoneBlock.instanceTo(self.newBlockNode)
        elif type == 'wood':
            self.woodLog.instanceTo(self.newBlockNode)
        elif type == 'planks':
            self.woodPlanks.instanceTo(self.newBlockNode)
        elif type == 'leaves':
            self.leavesBlock.instanceTo(self.newBlockNode)
            self.newBlockNode.setTransparency(TransparencyAttrib.MAlpha)
            self.newBlockNode.setBin('transparent', 0)
            self.newBlockNode.setDepthOffset(-1)
        elif type == 'glass':
            self.glassBlock.instanceTo(self.newBlockNode)
            self.newBlockNode.setTransparency(TransparencyAttrib.MAlpha)
            self.newBlockNode.setBin('transparent', 0)
            self.newBlockNode.setDepthOffset(-1)
        elif type == 'cobblestone':
            self.cobbleBlock.instanceTo(self.newBlockNode)
        elif type == 'crafting Table':
            self.craftingTable.instanceTo(self.newBlockNode)
        elif type == 'poppy':
            self.poppy.instanceTo(self.newBlockNode)
            self.newBlockNode.setTransparency(TransparencyAttrib.MAlpha)
            self.newBlockNode.setBin('transparent', 0)
            self.newBlockNode.setDepthOffset(-1)      
        
    def loadModels(self):
        self.grassBlock = self.loader.loadModel('grass-block.glb')
        self.dirtBlock = self.loader.loadModel('dirt-block.glb')
        self.stoneBlock = self.loader.loadModel('stone-block.glb')
        self.sandBlock = self.loader.loadModel('sand-block.glb')
        self.woodLog = self.loader.loadModel('wood-block.glb')
        self.woodPlanks = self.loader.loadModel('planks-block.glb')
        self.leavesBlock = self.loader.loadModel('leaves-block.glb')
        self.glassBlock = self.loader.loadModel('glass-block.glb')
        self.cobbleBlock = self.loader.loadModel('cobblestone-block.glb')
        self.stick = self.loader.loadModel('stick-item.glb')
        self.craftingTable = self.loader.loadModel('crafting Table-block.glb')
        self.poppy = self.loader.loadModel('poppy-block.glb')
        self.poppyItem = self.loader.loadModel('poppy-item.glb')

    def setupLights(self):
        mainLight = DirectionalLight('main light')
        mainLightNodePath = self.render.attachNewNode(mainLight)
        mainLightNodePath.setHpr(30, -60, 0)
        self.render.setLight(mainLightNodePath)

        ambientLight = AmbientLight('ambient light')
        ambientLight.setColor((0.3, 0.3, 0.3, 1))
        ambientLightNodePath = self.render.attachNewNode(ambientLight)
        self.render.setLight(ambientLightNodePath)

game = MyGame()
game.run()