window.myNamespace = Object.assign({}, window.myNamespace, {
    tabulator: {
        rowFormat: function(row) {
            row.getElement().classList.add(row.getData()._class);
            row.height = 20
            console.log(row)
        },
        rowClick: function(e, row) {
            row.treeToggle();
        },
        diagramIconColFormat: function(cell, formatterParams, onRendered) {
            return "<i class='bi bi-diagram-2' style='font-size:1.0rem'></i>";
        },
        diagramIconCellClick: function(e, cell) {
            const uuid = cell.getRow().getData()._uuid
            const event = new CustomEvent("clickDiagramIcon", { detail: uuid })
            document.dispatchEvent(event)
            e.cancelBubble = true
        }
    },
    dash: {
        toggleReactive: function(gd, ev) {
            console.log(gd)
        }
    }
})