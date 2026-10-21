# 用 Word 本身開啟 docx：更新目錄與欄位、重新分頁，回報總頁數與各章節起始頁，並另存 PDF。
# 用法：pwsh scripts/count_pages.ps1 -Path report/midterm/build/midterm.docx
param([Parameter(Mandatory = $true)][string]$Path)

$full = (Resolve-Path $Path).Path
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($full)
    foreach ($toc in $doc.TablesOfContents) {
        $toc.Update()
        # 目錄維持 1 頁：單行距、無段距、11pt（封面與目錄算在 25 頁內）
        $toc.Range.ParagraphFormat.LineSpacingRule = 0   # wdLineSpaceSingle
        $toc.Range.ParagraphFormat.SpaceBefore = 0
        $toc.Range.ParagraphFormat.SpaceAfter = 0
        $toc.Range.Font.Size = 11
    }
    $null = $doc.Fields.Update()
    $doc.Repaginate()
    $total = $doc.ComputeStatistics(2)   # wdStatisticPages

    # 每個標題在目錄裡也會出現，所以取「最後一次出現」的頁碼（正文）
    function Get-LastPage([string]$text) {
        $page = -1
        $rng = $doc.Content
        $find = $rng.Find
        $find.ClearFormatting()
        $find.Text = $text
        $find.Forward = $true
        $find.Wrap = 0   # wdFindStop
        while ($find.Execute()) {
            $page = $rng.Information(3)   # wdActiveEndPageNumber
            $rng.Collapse(0)              # wdCollapseEnd
        }
        return $page
    }
    $p1 = Get-LastPage "一、研究計畫之背景及目的"
    $p2 = Get-LastPage "二、研究方法、進行步驟及執行進度"
    $p22 = Get-LastPage "2. 預計可能遭遇之困難及解決途徑"
    $p3 = Get-LastPage "三、預期完成之工作項目、成果及績效"

    $pdf = [System.IO.Path]::ChangeExtension($full, ".pdf")
    $doc.SaveAs2($pdf, 17)   # wdFormatPDF
    $doc.Save()
    $doc.Close()

    [pscustomobject]@{
        total_pages         = $total
        start_ch1           = $p1
        start_ch2           = $p2
        start_ch2_2         = $p22
        start_ch3           = $p3
        methods_2_1_pages   = $p22 - $p2              # 「二、1.」：從「二、」起始頁到「二、2.」前一頁
        ch1_pages           = $p2 - $p1
        body_plus_refs      = $total - 2              # 扣掉封面與目錄
        pdf                 = $pdf
    } | ConvertTo-Json
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
