# Builds ../dist/climate-gesture.apk without Gradle: javac -> d8 -> aapt2 link -> zipalign -> apksigner.
$ErrorActionPreference = 'Stop'
$here  = $PSScriptRoot
$sdk   = 'D:\android-mitm\sdk'
$bt    = "$sdk\build-tools\34.0.0"
$jar   = "$sdk\platforms\android-34\android.jar"
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot'
$jdk   = "$env:JAVA_HOME\bin"
$out   = "$here\build"
$apk   = "$here\..\dist\climate-gesture.apk"

Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$out\classes", "$out\dex" | Out-Null

$srcs = Get-ChildItem "$here\src" -Recurse -Filter *.java | % FullName
& "$jdk\javac.exe" --release 8 -encoding UTF-8 -nowarn -classpath $jar -d "$out\classes" @srcs
if ($LASTEXITCODE) { throw 'javac failed' }

$classes = Get-ChildItem "$out\classes" -Recurse -Filter *.class | % FullName
& "$bt\d8.bat" --release --min-api 26 --lib $jar --output "$out\dex" @classes
if ($LASTEXITCODE) { throw 'd8 failed' }

& "$bt\aapt2.exe" link -o "$out\base.apk" -I $jar --manifest "$here\AndroidManifest.xml"
if ($LASTEXITCODE) { throw 'aapt2 failed' }

# add classes.dex (jar tool: update, no manifest)
Push-Location "$out\dex"
& "$jdk\jar.exe" -uMf "$out\base.apk" classes.dex
Pop-Location
if ($LASTEXITCODE) { throw 'jar failed' }

& "$bt\zipalign.exe" -f -p 4 "$out\base.apk" "$out\aligned.apk"
if ($LASTEXITCODE) { throw 'zipalign failed' }

$ks = "$here\debug.keystore"
if (-not (Test-Path $ks)) {
    & "$jdk\keytool.exe" -genkeypair -keystore $ks -storepass android -keypass android -alias cp60 `
        -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=climategesture' | Out-Null
}
& "$bt\apksigner.bat" sign --ks $ks --ks-pass pass:android --key-pass pass:android --out $apk "$out\aligned.apk"
if ($LASTEXITCODE) { throw 'apksigner failed' }
& "$bt\apksigner.bat" verify $apk
Remove-Item "$apk.idsig" -ErrorAction SilentlyContinue
Write-Host "built $apk"
