window.myNamespace = Object.assign({}, window.myNamespace, {
    tabulator: {
        rowFormat: function (row) {
            row.getElement().classList.add(row.getData()._class);
            row.height = 20
        },
        rowClick: function (e, row) {
            function expand(r) {
                r.treeToggle();
                console.log(r.getTreeChildren())
                if (r.getData()?._children?.length === 1)
                    expand(r.getTreeChildren()[0]);
            }
            expand(row);
        },
        diagramIconColFormat: function (cell, formatterParams, onRendered) {
            if (cell.getRow().getData()?._children)
                return "<i class='bi bi-diagram-2' title='Display Graph' style='font-size:1.0rem'></i>";
        },
        diagramIconCellClick: function (e, cell) {
            if (!cell.getRow().getData()?._children)
                return
            const uuid = cell.getRow().getData()._uuid
            console.log(cell.getRow().getData())
            console.log(uuid)
            const event = new CustomEvent("clickDiagramIcon", {detail: uuid})
            document.dispatchEvent(event)
            e.cancelBubble = true
        },
        infoIconColFormat: function (cell, formatterParams, onRendered) {
            if (cell.getRow().getData()?.url)
                return "<i class='bi bi-info-circle' title='Display Job Info' style='font-size:1.0rem'></i>";
        },
        statusCellFormat: function (cell, formatterPrams, onRendered) {
            rowData = cell.getRow().getData()
            cell.getElement().style.background = `linear-gradient(315deg, ${rowData._color[1]}, ${rowData._color[1]} 10px, ${rowData._color[0]} 10px, ${rowData._color[0]})`
            cell.getElement().style.color = "#fff"
            return cell.getValue()
            // return cell.getData()
            // return element
        },
        infoIconCellClick: function (e, cell) {
            console.log("infoIconCellClick")
            if (!cell.getRow().getData()?.url)
                return
            const uuid = cell.getRow().getData()._uuid
            const event = new CustomEvent("clickInfoIcon", {detail: uuid})
            document.dispatchEvent(event)
            e.cancelBubble = true
        },
        nameHeaderFilter: function (headerValue, rowValue, rowData, filterParams) {
            re = new RegExp(headerValue, 'i');
            rowMatch = re.test(rowValue);

            function filt(rd) {
                return re.test(rd.name) || rd?._children?.some(filt);
            }

            return filt(rowData);
        },
        serialHeaderFilter: function (headerValue, rowValue, rowData, filterParams) {
            re = new RegExp(headerValue, 'i');
            rowMatch = re.test(rowValue);

            function filt(rd) {
                return re.test(rd.serial) || rd?._children?.some(filt);
            }

            return filt(rowData);
        },
        statusHeaderFilter: function (headerValue, rowValue, rowData, filterParams) {
            function filt(rd) {
                return rd.status === headerValue || rd?._children?.some(filt);
            }

            return filt(rowData);
        },
    },
})