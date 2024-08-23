function doPost(e) {
    const KEY = '自己設定一組亂數'; // 設置你的 script 密鑰
    const FolderId = '從分享連結取得'; // 替換為你的 Google Drive 文件夾 ID

    try {
        // 檢查是否包含必要的參數
        if (!e.parameter.scriptKey || !e.parameter.fileName || !e.parameter.fileContent) {
            throw new Error('Error: Missing required parameters. Please provide scriptKey, fileName and fileContent.');

            // 檢查 script 密鑰
        } else if (e.parameter.scriptKey !== KEY) {
            throw new Error('Error: Unauthorized. Invalid scriptKey.');
        }

        var fileName = e.parameter.fileName;
        var fileContent = e.parameter.fileContent;

        var blob = Utilities.newBlob(fileContent, 'text/html', fileName);

        var folder = DriveApp.getFolderById(FolderId);
        var file = folder.createFile(blob);

        // 返回成功的響應
        return ContentService.createTextOutput('File uploaded successfully. File ID: ' + file.getId())
            .setMimeType(ContentService.MimeType.TEXT);

    } catch (error) {
        // 返回錯誤的響應
        throw new Error('Error: ' + error.message);
    }
}