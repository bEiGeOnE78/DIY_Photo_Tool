# 📚 DIY Photo Tool - Keyboard Shortcuts Cheatsheet

Complete reference for all keyboard shortcuts in the DIY Photo Management Toolkit web interface.

## 🎯 Quick Reference

| Shortcut | Function |
|----------|----------|
| `/` | Open command palette |
| `Q` | Exit/back/clear selection |
| `Space` | Toggle zoom modes / Enter cull mode |
| `M` | Toggle metadata sidebar |
| `G` | Toggle gallery selector |
| `L` | Toggle picks list |
| `P` | Mark as pick |
| `X` | Mark as reject |
| `O` | Toggle face detection overlay |
| `S` | Toggle status feed log |

---

## 🖼️ Navigation Shortcuts

### **Arrow Keys - Image Navigation**
- `←` **Left Arrow** - Previous image/thumbnail
- `→` **Right Arrow** - Next image/thumbnail  
- `↑` **Up Arrow** - Move up in thumbnail grid
- `↓` **Down Arrow** - Move down in thumbnail grid

### **Modifier Combinations**
- `Shift + ←/→` - Navigate with range selection
- `Shift + ↑/↓` - Vertical navigation with selection
- `Ctrl/Cmd + Click` - Toggle individual thumbnail selection
- `Shift + Click` - Range selection from last selected

---

## 🔍 View Modes & Zoom

### **View Mode Switching**
- `Space` - **Primary zoom toggle**:
  - In **Thumbnail mode**: Enter single view or cull mode
  - In **Fit mode**: Enter zoom mode
  - In **Zoom mode**: Exit to fit mode
- `Q` - **Exit/Back**:
  - In **Zoom mode**: Exit to fit mode
  - In **Fit mode**: Return to thumbnails  
  - In **Thumbnail mode**: Clear all selections

### **Cull Mode (Multi-image Review)**
*Activated by pressing `Space` with multiple selected thumbnails*

| Key | Action |
|-----|--------|
| `←/→` | Navigate between selected images |
| `Space` | Toggle zoom in/out |
| `P` | Mark current image as pick |
| `F` | Mark for deletion and exit |
| `Q` | Exit cull mode without changes |

---

## 🏷️ Image Organization

### **Pick/Reject System**
- `P` - **Mark as Pick** (⭐ star the image)
- `X` - **Mark as Reject** (❌ mark for potential deletion)

*Picks and rejects are saved to JSON files and can be processed via command palette*

---

## 🎛️ Interface Controls

### **Sidebar & Panels**
- `M` - **Toggle Metadata Sidebar** 
  - Shows EXIF data, GPS info, camera settings
  - Includes face detection information
- `G` - **Toggle Gallery Selector**
  - Quick switcher between galleries
- `L` - **Toggle Picks List**
  - View all starred images in current gallery
- `S` - **Toggle Status Feed Log**
  - Real-time processing updates

### **Overlays & Detection**
- `O` - **Toggle Face Detection Overlay**
  - Shows detected faces with names/labels
  - Requires face recognition to be processed

---

## 🎨 Command Palette

### **Opening & Navigation**
- `/` - **Open Command Palette** (Spotlight-style)
- `Escape` - Close command palette or exit gallery mode
- `↑/↓` - Navigate command suggestions
- `Enter` - Execute selected command

### **Available Commands**
Type these commands in the palette:

| Command | Function |
|---------|----------|
| `gallery` | Create new gallery with smart search |
| `process` | Process new images (complete workflow) |
| `regenerate` | Regenerate RAW picks with custom settings |
| `delete` | Delete rejected images (safe preview) |
| `stats` | View comprehensive database statistics |
| `rebuild` | Rebuild current gallery JSON |
| `list` | Rebuild main galleries list |

---

## 🖱️ Mouse & Touch Interactions

### **Thumbnail Grid**
- **Single Click** - Select thumbnail
- **Ctrl/Cmd + Click** - Toggle selection
- **Shift + Click** - Range selection
- **Double Click** - Open in single view

### **Single Image View**
- **Click & Drag** - Pan around zoomed image
- **Scroll Wheel** - Zoom in/out
- **Touch Gestures** - Pinch to zoom, swipe to navigate

---

## 💡 Pro Tips

### **Efficient Workflows**

1. **Quick Gallery Creation**:
   - Press `/` → type "gallery" → Enter
   - Use natural language: "John 2024 fuji"

2. **Batch Photo Review**:
   - Select multiple thumbnails
   - Press `Space` to enter cull mode
   - Use `←/→` + `P`/`F` for quick decisions

3. **Pick Management**:
   - Mark favorites with `P`
   - View all picks with `L`
   - Process picks via `/` → "regenerate"

4. **Face Recognition Workflow**:
   - Toggle faces with `O`
   - Use metadata sidebar (`M`) to see face details
   - Process faces via command palette

### **Keyboard Shortcut Conflicts**

- **Avoid shortcuts when**:
  - Input fields are focused (except command palette)
  - Text is being entered in search boxes
  - Command palette is open (different key behavior)

### **Context-Sensitive Behavior**

- `Space` changes behavior based on current mode
- `Q` always means "go back" or "exit current state"
- Arrow keys work differently in thumbnails vs single view
- Modifier keys (Shift/Ctrl) extend selection behavior

---

## 🎮 Gaming-Style Navigation

The interface is designed for fast, keyboard-centric operation:

- **WASD Alternative**: Arrow keys for movement
- **ESC to Exit**: Universal back/cancel
- **Space as Action**: Context-sensitive primary action
- **Slash for Search**: Universal command access
- **Letter Keys**: Single-key actions (M, G, L, P, X, O, S)

---

## 🔧 Customization Notes

### **Where Shortcuts Are Defined**

All keyboard shortcuts are defined in `index-display.html` around **line 4477** in the main `keydown` event listener:

```javascript
document.addEventListener("keydown", (e) => {
  // Shortcut definitions here
  if (e.key === "m") toggleSidebar();
  if (e.key === "p") togglePick();
  // ... etc
});
```

### **Adding Custom Shortcuts**

To add new shortcuts:
1. Edit the `keydown` event listener in `index-display.html`
2. Add your key check: `if (e.key === "your-key") yourFunction();`
3. Make sure to prevent default behavior: `e.preventDefault();`
4. Test that it doesn't conflict with existing shortcuts

---

## 📱 Mobile/Touch Considerations

- Most keyboard shortcuts don't apply on touch devices
- Touch gestures replace keyboard navigation:
  - **Swipe** - Navigate between images
  - **Pinch** - Zoom in/out
  - **Tap** - Select/interact
  - **Long press** - Context actions

---

## 🚨 Troubleshooting

### **Shortcuts Not Working?**

1. **Check for focused inputs** - Click outside input fields
2. **Close command palette** - Press `Escape`
3. **Refresh page** - Sometimes JavaScript state gets confused
4. **Check browser compatibility** - Modern browsers required
5. **Look for JavaScript errors** - Check browser console (F12)

### **Common Issues**

- **Arrow keys scroll page**: Make sure focus is on gallery, not browser
- **Letters type in address bar**: Click in the gallery area first
- **Shortcuts work intermittently**: Avoid rapid key presses
- **Face detection not toggling**: Ensure face processing is complete

---

*Last Updated: 2025-08-25*
*For more help, see `README.md` or `API_Reference.org`*