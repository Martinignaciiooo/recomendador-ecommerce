param([Parameter(Mandatory=$true)][string]$InputDocx,[Parameter(Mandatory=$true)][string]$OutputPdf)
$ErrorActionPreference='Stop'
$inputPath=(Resolve-Path -LiteralPath $InputDocx).Path
$outputPath=[IO.Path]::GetFullPath($OutputPdf)
$wordApp=$null
$reportDoc=$null
try {
  $wordApp=New-Object -ComObject Word.Application
  $wordApp.Visible=$false
  $wordApp.DisplayAlerts=0
  $wordApp.AutomationSecurity=3
  $reportDoc=$wordApp.Documents.Open($inputPath,$false,$true)
  $reportDoc.ExportAsFixedFormat($outputPath,17)
  Write-Output ('PAGES='+$reportDoc.ComputeStatistics(2))
} finally {
  if ($null -ne $reportDoc) {$reportDoc.Close(0);[void][Runtime.InteropServices.Marshal]::ReleaseComObject($reportDoc)}
  if ($null -ne $wordApp) {$wordApp.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp)}
}
