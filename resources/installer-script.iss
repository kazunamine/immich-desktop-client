; Inno Setup script for ぶいちゃフォト (buicha-photo)
; Collects the API key and watch folder during installation, writes config.yaml,
; and registers the app to start with Windows.

#define MyAppName "ぶいちゃフォト"
#define MyAppVersion "2026.06.15.1"
#define MyAppPublisher "buicha.jp"
#define MyAppURL "https://photos.buicha.jp/"
#define MyAppExeName "buicha-photo.exe"
#define MyImmichApiUrl "https://photos.buicha.jp/api"
#define MyDefaultAlbum "Desktop"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
AppId={{B7E5B1F4-2C3A-4D6E-9A81-3F0C5D8E12A4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={%USERPROFILE}\.buicha-photo
DisableDirPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
; Install for the current user only (no administrator rights required).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
OutputDir=..\dist
OutputBaseFilename=buicha-photo-installer
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Registry]
; Register per-user auto-start without requiring administrator privileges.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "BuichaPhoto"; ValueData: """{app}\{#MyAppExeName}"" --autostart"; Flags: uninsdeletevalue

[InstallDelete]
; Remove Startup-folder shortcuts created by older installer versions.
Type: files; Name: "{userstartup}\{#MyAppName}.lnk"
Type: files; Name: "{userstartup}\ImmichAutoStart.lnk"
Type: files; Name: "{userstartup}\Immich Desktop Client.lnk"
Type: files; Name: "{userstartup}\immich-desktop-client.lnk"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the config / shelve / log files generated at runtime so uninstall is clean.
Type: filesandordirs; Name: "{app}"

[Code]
var
  ApiKeyPage: TInputQueryWizardPage;
  WatchDirPage: TInputDirWizardPage;

function GetDefaultWatchDir: String;
var
  Pics: String;
begin
  // Inno Setup has no {userpics} constant; resolve the Pictures folder via CSIDL.
  Pics := GetShellFolderByCSIDL($0027, False); // CSIDL_MYPICTURES
  if Pics = '' then
    Pics := ExpandConstant('{%USERPROFILE}\Pictures');
  Result := AddBackslash(Pics) + 'VRChat';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // Auto-started copies may lock the executables during an update.
  Exec('taskkill.exe', '/F /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('taskkill.exe', '/F /IM immich-desktop-client.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

procedure InitializeWizard;
begin
  ApiKeyPage := CreateInputQueryPage(wpWelcome,
    'APIキーの入力',
    'ぶいちゃフォトのAPIキーを入力してください。',
    'photos.buicha.jp の設定画面で発行したAPIキーを貼り付けてください。アップロード先のサーバーは自動的に設定されます。');
  ApiKeyPage.Add('APIキー:', False);

  WatchDirPage := CreateInputDirPage(ApiKeyPage.ID,
    '監視フォルダの選択',
    'アップロードしたい写真が保存されるフォルダを選択してください。',
    'このフォルダに新しく追加された画像・動画が自動的にアップロードされます。通常はVRChatの保存先（Pictures\VRChat）のままで問題ありません。',
    False, '');
  WatchDirPage.Add('監視するフォルダ:');
  WatchDirPage.Values[0] := GetDefaultWatchDir;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ApiKeyPage.ID then
  begin
    if Trim(ApiKeyPage.Values[0]) = '' then
    begin
      MsgBox('APIキーを入力してください。', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigLines: TArrayOfString;
  WatchDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    WatchDir := WatchDirPage.Values[0];
    ForceDirectories(WatchDir);

    SetArrayLength(ConfigLines, 8);
    ConfigLines[0] := 'api:';
    ConfigLines[1] := '  key: ' + Trim(ApiKeyPage.Values[0]);
    ConfigLines[2] := '  url: {#MyImmichApiUrl}';
    ConfigLines[3] := '  album: {#MyDefaultAlbum}';
    ConfigLines[4] := 'watchdog:';
    ConfigLines[5] := '  directories:';
    ConfigLines[6] := '    - |-';
    ConfigLines[7] := '      ' + WatchDir;

    if not SaveStringsToUTF8File(
      ExpandConstant('{app}\config.yaml'), ConfigLines, False) then
      RaiseException('設定ファイルを保存できませんでした。');
  end;
end;
