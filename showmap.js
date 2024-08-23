function doGet(e) {
    var fileName = e.parameter.fileName; // 從 URL 參數獲取檔案名
    if (fileName) {
        var file = getFileByName(fileName);
        if (file) {
            var htmlContent = file.getBlob().getDataAsString();
            return HtmlService.createHtmlOutput(htmlContent)
                .setTitle('Dynamic HTML Viewer');
        } else {
            return HtmlService.createHtmlOutput('File not found.');
        }
    } else {
        return HtmlService.createHtmlOutput('No file name provided.');
    }
}

function getFileByName(fileName) {
    var folderId = '從分享連結取得'; // 替換為你的共用資料夾ID
    var folder = DriveApp.getFolderById(folderId);
    var files = folder.getFilesByName(fileName);
    return files.hasNext() ? files.next() : null;
}
