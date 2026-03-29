; NeatCopy Inno Setup Script
; 用于生成 Windows 安装向导程序

#define AppName "NeatCopy"
#define AppVersion "1.5.0"
#define AppPublisher "NeatCopy"
#define AppURL "https://github.com/StoneLL1/NeatCopy"
#define AppExeName "NeatCopy.exe"
#define SourceExe "..\dist\NeatCopy.exe"
#define AppIcon "..\assets\idle.ico"

[Setup]
AppId={{6F8A3C9D-4B2E-4F1A-8D5C-3E7B9A0F6D12}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
; 输出目录和文件名
OutputDir=Output
OutputBaseFilename=NeatCopy_Setup_v{#AppVersion}
; 安装程序图标
SetupIconFile={#AppIcon}
; 压缩
Compression=lzma2/ultra64
SolidCompression=yes
; UAC - keyboard 库需要管理员权限
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
; 安装向导外观
WizardStyle=modern
; 最低 Windows 版本要求（Windows 10）
MinVersion=10.0
; 卸载显示图标
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
; 桌面（可选）
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸载时关闭正在运行的 NeatCopy
Filename: "taskkill"; Parameters: "/F /IM {#AppExeName}"; Flags: runhidden; RunOnceId: "KillNeatCopy"
