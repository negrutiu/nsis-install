!define /ifndef TARGET "x86-unicode"
Target ${TARGET} ; "x86-unicode", "amd64-unicode"

!define /ifndef SUFFIX ""
Name "Test${SUFFIX}"
OutFile "Test${SUFFIX}.exe"
InstallDir "$TEMP"
ManifestDPIAware true
RequestExecutionLevel user
ShowInstDetails show

!include /nonfatal "ModernXL.nsh"
!include "MUI2.nsh"
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\nsis-menu.ico"

;!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${__FILE__}"
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section -
    DetailPrint '-- This is a demo project'
    DetailPrint '-- No files and/or registry keys were modified'
SectionEnd