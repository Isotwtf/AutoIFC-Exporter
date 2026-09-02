# -*- coding: utf-8 -*-
"""
Enumeration of IFC Export Setups.

Revit's *named* IFC export setups (the ones a user creates and tunes
via File > Export > IFC > Modify Setup, and that show up in the
Export IFC dialog's "Setup" dropdown) are NOT part of the core
RevitAPI. They belong to the IFC exporter UI component that ships in
the box with Revit, historically an `IFCExportConfigurationsMap` type
in a `Revit.IFC.Export.UI.dll` / `BIM.IFC.Export.UI` namespace pairing
-- but that assembly/namespace naming has shifted across Revit
versions, and the DLL is only loaded into the process the first time
Revit's own File > Export > IFC command runs in a session (external
COMMANDS load lazily, unlike external APPLICATIONS).

Both of those facts matter for how this module is written:

1. We search for the type by NAME across whatever is already loaded
   in the process, instead of hardcoding an assembly/namespace and
   importing it -- so a naming difference on your Revit version can't
   silently defeat detection.
2. That search runs FRESH every time get_ifc_export_setups() is
   called, never cached at module import time. pyRevit keeps lib/
   modules loaded in memory across button clicks within a session, so
   a check that only ran once at import time would permanently miss
   the DLL if it loaded only after this module was first imported --
   exactly the "opened Export > IFC afterwards and it still didn't
   work" scenario.
3. Rather than requiring you to manually open File > Export > IFC once
   per session just to get that DLL loaded, _preload_ifc_export_ui()
   below finds and loads it ourselves, from disk, the moment this tool
   runs -- it's the exact same file Revit's own menu command would
   load, we're just not waiting for an unrelated menu click to trigger
   it. This only loads a file Autodesk shipped as part of your own
   Revit installation; it never opens a dialog, downloads anything, or
   touches the document, so a failure here can only ever mean "fall
   back to the generic list below" -- it cannot destabilize Revit.
"""
import os

import clr
clr.AddReference("System")
import System

try:
    clr.AddReference("PresentationFramework")
    clr.AddReference("WindowsBase")
    import System.Windows
    import System.Windows.Threading
    _HAS_WPF = True
except Exception:
    _HAS_WPF = False

from Autodesk.Revit.DB import IFCExportOptions, IFCVersion


# Cache for _find_ifc_export_ui_dll_path()'s result ONLY -- this is
# safe to cache (unlike whether the assembly is loaded, which is what
# get_ifc_export_setups() deliberately never caches) because the DLL's
# location on disk is static for the life of a Revit session, whereas
# "is it loaded yet" changes as a side effect of things the user does.
# Avoids re-walking the entire Revit install directory on every call.
_cached_ifc_export_ui_dll_path = None

# Generic fallback list used only when Revit's native named setups
# could not be found in this session.
_FALLBACK_IFC_VERSIONS = [
    ("IFC 2x3 Coordination View 2.0", IFCVersion.IFC2x3CV2),
    ("IFC 4 Reference View", IFCVersion.IFC4RV),
    ("IFC 2x3", IFCVersion.IFC2x3),
    ("IFC 4", IFCVersion.IFC4),
]


class IFCSetupInfo(object):
    """
    One selectable entry in the "Select IFC Export Setup" UI.

    `configuration` holds the live IFCExportConfiguration .NET object
    when a named project setup was found; it is None for the generic
    fallback entries, in which case `ifc_version` is used instead.
    """

    def __init__(self, name, configuration=None, ifc_version=None):
        self.name = name
        self.configuration = configuration
        self.ifc_version = ifc_version

    def __str__(self):
        # pyrevit.forms.SelectFromList displays str(item) by default.
        return self.name


def _find_ifc_export_ui_dll_path():
    """
    Locate the IFC exporter UI DLL on disk without hardcoding an exact
    file name (it has varied: Revit.IFC.Export.UI.dll historically,
    Autodesk.IFC.Export.UI.dll on Revit 2027). We find Revit's own
    install directory via an already-loaded core assembly (RevitAPI,
    always present) and search it for any DLL whose name contains
    "ifc", "export", and "ui" -- narrow enough to avoid false matches,
    loose enough to survive a rename.

    Result is cached at module level (see _cached_ifc_export_ui_dll_path)
    since this involves walking the whole Revit install directory and
    the answer can't change within a session.
    """
    global _cached_ifc_export_ui_dll_path
    if _cached_ifc_export_ui_dll_path is not None:
        return _cached_ifc_export_ui_dll_path

    try:
        revit_api_asm = None
        for asm in System.AppDomain.CurrentDomain.GetAssemblies():
            try:
                if (asm.GetName().Name or "") == "RevitAPI":
                    revit_api_asm = asm
                    break
            except Exception:
                continue
        if revit_api_asm is None:
            return None
        install_dir = os.path.dirname(revit_api_asm.Location)
    except Exception:
        return None

    try:
        for root, _dirs, files in os.walk(install_dir):
            for file_name in files:
                lower = file_name.lower()
                if lower.endswith(".dll") and "ifc" in lower and "export" in lower and "ui" in lower:
                    _cached_ifc_export_ui_dll_path = os.path.join(root, file_name)
                    return _cached_ifc_export_ui_dll_path
    except Exception:
        return None
    return None


def _preload_ifc_export_ui(diagnostics):
    """
    Load the IFC exporter UI DLL ourselves, from disk, instead of
    requiring you to open Revit's native File > Export > IFC once per
    session first. Safe to call even if it's already loaded -- .NET
    recognizes the same assembly path and reuses what's already in
    memory rather than loading a duplicate copy.
    """
    dll_path = _find_ifc_export_ui_dll_path()
    if dll_path is None:
        diagnostics.append(
            "Could not locate an IFC export UI DLL under the Revit install "
            "directory to preload; falling back to whatever is already loaded."
        )
        return

    try:
        System.Reflection.Assembly.LoadFrom(dll_path)
        diagnostics.append("Preloaded IFC export UI assembly from: {}".format(dll_path))
    except Exception as ex:
        diagnostics.append("Preloading '{}' failed: {}".format(dll_path, ex))


def _find_configurations_map_candidates(diagnostics):
    """
    Find every assembly-hosted type literally named
    "IFCExportConfigurationsMap" across everything Revit has already
    loaded into this process (after _preload_ifc_export_ui() has had a
    chance to make sure that's not an empty set). Recent Revit versions
    split the old single IFC exporter assembly into several (e.g. a
    low-level "Revit.IFC.Export" engine assembly plus a dialog-facing
    "*.Export.UI" one), and more than one of them can define a type
    with this same name but a DIFFERENT API surface -- only the UI one
    tends to expose the classic dictionary-like AddSavedConfigurations
    (Document)/.Keys/[] surface that matches what Revit's own Export
    IFC dialog uses. So this returns every candidate, with "*.Export.UI"
    assemblies sorted first, and the caller tries each in turn until
    one actually works.
    """
    _preload_ifc_export_ui(diagnostics)

    assemblies = list(System.AppDomain.CurrentDomain.GetAssemblies())

    ifc_like = []
    for asm in assemblies:
        try:
            asm_name = asm.GetName().Name or ""
        except Exception:
            continue
        if "ifc" in asm_name.lower():
            ifc_like.append((asm_name, asm))

    diagnostics.append(
        "Loaded assemblies with 'ifc' in their name: {}".format(
            ", ".join(n for n, _ in ifc_like) or "(none)"
        )
    )

    # UI-facing assemblies first -- that's where the classic,
    # dictionary-like map implementation tends to live.
    ifc_like.sort(key=lambda item: (0 if "export.ui" in item[0].lower() else 1, item[0]))

    candidates = []
    for asm_name, asm in ifc_like:
        try:
            types = asm.GetTypes()
        except Exception as ex:
            # Partially-loadable assemblies still expose what did load.
            types = list(getattr(ex, "Types", None) or [])
        for t in types:
            if t is not None and t.Name == "IFCExportConfigurationsMap":
                candidates.append((asm_name, t))

    if candidates:
        diagnostics.append(
            "Found IFCExportConfigurationsMap candidate(s) in: {}".format(
                ", ".join(n for n, _ in candidates)
            )
        )
    else:
        diagnostics.append(
            "IFCExportConfigurationsMap was not found in any loaded assembly "
            "-- Revit's own IFC export UI has not been loaded into this "
            "session yet."
        )

    return candidates


def _construct_config_map(map_type, doc, diagnostics):
    """
    Construct an IFCExportConfigurationsMap instance, trying known
    constructor shapes in order:

      1. IFCExportConfigurationsMap(Document) -- confirmed against the
         Autodesk/revit-ifc source for Revit 2027 (Release_27.x.x):
         this is the ONLY step in Revit's own construction sequence
         that touches the Document, so this is where a project's
         persisted, named/saved setups actually get read from
         extensible storage.
      2. IFCExportConfigurationsMap() -- the parameterless, older
         shape, for Revit versions predating that refactor. Saved
         setups on that shape are loaded via a separate
         AddSavedConfigurations(...) call attempted afterwards by the
         caller.

    Returns (config_map, doc_loaded_via_constructor) or (None, False).
    """
    try:
        config_map = System.Activator.CreateInstance(map_type, doc)
        return config_map, True
    except Exception as ex:
        diagnostics.append("  new IFCExportConfigurationsMap(doc) failed: {}".format(ex))

    try:
        config_map = System.Activator.CreateInstance(map_type)
        return config_map, False
    except Exception as ex:
        diagnostics.append("  new IFCExportConfigurationsMap() failed: {}".format(ex))

    return None, False


def _enumerate_config_map(config_map, diagnostics):
    """
    Read every configuration out of a populated map, trying known
    access patterns in order: the modern `.Values` enumerable
    property, the older `.Keys` + indexer pair, and finally raw
    iteration as a last resort.
    """
    try:
        setups = [IFCSetupInfo(cfg.Name, configuration=cfg) for cfg in config_map.Values]
        if setups:
            return setups
        diagnostics.append("  '.Values' was present but empty.")
    except Exception as ex:
        diagnostics.append("  '.Values' not usable ({}); trying Keys/indexer.".format(ex))

    try:
        setups = [IFCSetupInfo(config_map[key].Name, configuration=config_map[key])
                  for key in config_map.Keys]
        if setups:
            return setups
        diagnostics.append("  '.Keys'/indexer was present but empty.")
    except Exception as ex:
        diagnostics.append("  '.Keys'/indexer not usable ({}); trying direct iteration.".format(ex))

    try:
        setups = []
        for entry in config_map:
            cfg = getattr(entry, "Value", entry)
            setups.append(IFCSetupInfo(cfg.Name, configuration=cfg))
        return setups
    except Exception as ex:
        diagnostics.append("  Direct iteration also failed: {}".format(ex))
        return []


def _find_type_by_name(type_name, preferred_assembly_name=None):
    """
    Find any loaded type with this exact simple name, searching the
    preferred assembly first (if given) since a type that belongs
    with our chosen IFCExportConfigurationsMap candidate should come
    from the same assembly.
    """
    assemblies = list(System.AppDomain.CurrentDomain.GetAssemblies())
    if preferred_assembly_name:
        assemblies.sort(
            key=lambda a: 0 if (a.GetName().Name or "") == preferred_assembly_name else 1
        )
    for asm in assemblies:
        try:
            types = asm.GetTypes()
        except Exception as ex:
            types = list(getattr(ex, "Types", None) or [])
        for t in types:
            if t is not None and t.Name == type_name:
                return t
    return None


def _count_configs(config_map):
    """Best-effort count for before/after diagnostics -- never raises."""
    try:
        return len(list(config_map.Values))
    except Exception:
        pass
    try:
        return len(list(config_map.Keys))
    except Exception:
        return -1


def _add_saved_configurations(config_map, asm_name, doc, diagnostics):
    """
    Load this project's persisted, named IFC Export Setups.

    Despite what its parameter type suggests, AddSavedConfigurations
    is the method that actually reads a project's saved setups from
    extensible storage (confirmed against the Revit 2027 source) --
    NOT the Document-argument constructor, which only associates the
    map with a document. This must run regardless of which
    constructor shape succeeded, or a project's custom setups get
    silently skipped in favor of only the built-in ones.
    """
    before = _count_configs(config_map)

    attempts = [
        ("AddSavedConfigurations(doc)", lambda: config_map.AddSavedConfigurations(doc)),
        ("AddSavedConfigurations(empty dict)", lambda: config_map.AddSavedConfigurations({})),
        ("AddSavedConfigurations()", lambda: config_map.AddSavedConfigurations()),
    ]

    cfg_type = _find_type_by_name("IFCExportConfiguration", preferred_assembly_name=asm_name)
    if cfg_type is not None:
        try:
            typed_empty = System.Collections.Generic.Dictionary[System.String, cfg_type]()
            attempts.append((
                "AddSavedConfigurations(typed empty Dictionary<string,IFCExportConfiguration>)",
                lambda: config_map.AddSavedConfigurations(typed_empty),
            ))
        except Exception as ex:
            diagnostics.append(
                "  Could not build a typed empty configurations dictionary: {}".format(ex)
            )

    for attempt, call in attempts:
        try:
            call()
            after = _count_configs(config_map)
            diagnostics.append(
                "  {} succeeded ({} -> {} configuration(s) in the map).".format(
                    attempt, before, after
                )
            )
            return
        except Exception as ex:
            diagnostics.append("  {} failed: {}".format(attempt, ex))

    diagnostics.append("  Could not load this project's saved setups via any known call.")


def _try_load_from_candidate(asm_name, map_type, doc, diagnostics):
    """
    Attempt the full read flow using ONE candidate type. Returns
    (setups, config_map) on success, or (None, None) if this
    particular type's API surface didn't pan out (caller moves on to
    the next candidate instead of giving up). The live config_map is
    returned too (not just the flattened IFCSetupInfo list) so a
    caller can later reopen Revit's own settings editor against it --
    see open_setup_editor().
    """
    diagnostics.append("Trying IFCExportConfigurationsMap from '{}':".format(asm_name))

    config_map, _doc_loaded_via_constructor = _construct_config_map(map_type, doc, diagnostics)
    if config_map is None:
        return None, None

    try:
        config_map.AddBuiltInConfigurations()
    except Exception as ex:
        diagnostics.append("  AddBuiltInConfigurations() failed: {}".format(ex))

    # Always attempt this -- see _add_saved_configurations docstring
    # for why it can't be skipped just because the Document-argument
    # constructor already succeeded.
    _add_saved_configurations(config_map, asm_name, doc, diagnostics)

    setups = _enumerate_config_map(config_map, diagnostics)
    if not setups:
        diagnostics.append("  This type produced zero configurations.")
        return None, None

    diagnostics.append("  Loaded {} configuration(s) from this type.".format(len(setups)))
    return setups, config_map


def _load_named_configurations(doc, diagnostics):
    """
    Try every candidate IFCExportConfigurationsMap type (see
    _find_configurations_map_candidates) until one produces a usable
    (setups, config_map) pair. Runs fresh on every call -- see module
    docstring for why that matters.
    """
    candidates = _find_configurations_map_candidates(diagnostics)
    for asm_name, map_type in candidates:
        setups, config_map = _try_load_from_candidate(asm_name, map_type, doc, diagnostics)
        if setups:
            return setups, config_map
    return [], None


def get_ifc_export_setups(doc):
    """
    Return (setups, used_native, diagnostics, config_map):
      - setups: list of IFCSetupInfo the user can pick from.
      - used_native: whether these came from Revit's real,
        project-specific IFC Export Setups (True) or the generic
        fallback list (False).
      - diagnostics: list of plain-English strings describing what
        detection did/found this call -- useful to log or show when
        used_native is False and the reason isn't obvious.
      - config_map: the live IFCExportConfigurationsMap .NET object
        when used_native is True (None otherwise) -- pass this to
        open_setup_editor() to let the user tune settings via Revit's
        own native editor before exporting.
    """
    diagnostics = []
    named, config_map = _load_named_configurations(doc, diagnostics)
    if named:
        return named, True, diagnostics, config_map

    fallback = [IFCSetupInfo(name, ifc_version=version)
                for name, version in _FALLBACK_IFC_VERSIONS]
    return fallback, False, diagnostics, None


def _set_static_document_context(type_name, doc, diagnostics, preferred_assembly_name=None):
    """
    Some features inside IFCExporterUIWindow (confirmed: the "Import
    setup..." button's click handler, Classification Settings, Project
    Address, and the Category/Property Mapping editors) read a
    Document from a static property on ANOTHER class
    (IFCExport.TheDocument / IFCCommandOverrideApplication.TheDocument)
    rather than from the configurations map we control -- because in
    Revit's own flow, those get set as a side effect of constructing
    the main Export IFC dialog first, which we deliberately skip (see
    open_setup_editor). Left unset, that static Document is null, and
    the handlers that use it don't null-check, so the exception
    unwinds the whole modal window (looks like the dialog just
    closing). Priming these before showing the editor avoids that.

    Best-effort and non-fatal by design: if a given type/member isn't
    found (naming can vary by Revit version), we just move on --
    core config editing already works without this; only a few
    secondary features need it. Every attempt is logged, INCLUDING a
    plain type-not-found miss, specifically so a silent failure here
    (the property genuinely didn't get set) is distinguishable from
    "it was set but something else is still broken".
    """
    t = _find_type_by_name(type_name, preferred_assembly_name=preferred_assembly_name)
    if t is None:
        diagnostics.append("  Type '{}' not found -- cannot prime its TheDocument.".format(type_name))
        return

    # BindingFlags.Static, on its own, only looks at members declared
    # DIRECTLY on this type -- inherited static members need
    # FlattenHierarchy too, and we don't know this class's exact
    # inheritance shape, so include it defensively.
    flags = (System.Reflection.BindingFlags.Public
             | System.Reflection.BindingFlags.NonPublic
             | System.Reflection.BindingFlags.Static
             | System.Reflection.BindingFlags.FlattenHierarchy)

    try:
        prop = t.GetProperty("TheDocument", flags)
        if prop is not None:
            if prop.CanWrite:
                prop.SetValue(None, doc, None)
                diagnostics.append("  Primed {}.TheDocument (property).".format(type_name))
                return
            diagnostics.append(
                "  {}.TheDocument is a read-only property -- cannot set it this way.".format(type_name)
            )
    except Exception as ex:
        diagnostics.append("  Priming {}.TheDocument (property) failed: {}".format(type_name, ex))

    try:
        field = t.GetField("TheDocument", flags)
        if field is not None:
            field.SetValue(None, doc)
            diagnostics.append("  Primed {}.TheDocument (field).".format(type_name))
            return
    except Exception as ex:
        diagnostics.append("  Priming {}.TheDocument (field) failed: {}".format(type_name, ex))

    diagnostics.append(
        "  Type '{}' was found but has no 'TheDocument' property or field we could set "
        "(name may differ on this Revit version).".format(type_name)
    )


def open_setup_editor(config_map, initial_setup_name, doc, diagnostics):
    """
    Show Revit's own "Modify Setup" editor window (IFCExporterUIWindow
    -- the exact class behind File > Export > IFC > Modify Setup...)
    pre-loaded with the configuration named initial_setup_name inside
    config_map, so the user can tune category mapping, property
    mapping, level of detail, geographic reference, etc. through the
    real native UI instead of us reimplementing any of it.

    The window's own left-hand panel lets the user browse and select
    ANY configuration in config_map, not just initial_setup_name --
    that's the same full picker Revit's native dialog uses, so a
    separate "choose a setup" step before this one would just be
    duplicate UI. Whatever the user is looking at when they click OK
    is what should be used, which may not be initial_setup_name
    anymore. IFCExporterUIWindow tracks that internally via a PRIVATE
    GetSelectedConfiguration() method (there's no public property for
    it), so we invoke it via reflection with NonPublic binding flags
    to read back the real answer; if that fails for any reason we
    fall back to re-reading initial_setup_name from the map, which is
    at least correct for the "didn't browse away" case.

    Returns the resulting IFCExportConfiguration on OK, or None if the
    user cancelled or the window type/construction wasn't available
    (the caller should fall back to using its own baseline
    configuration unmodified in that case, never block the export
    over this).
    """
    window_type = _find_type_by_name("IFCExporterUIWindow")
    if window_type is None:
        diagnostics.append(
            "IFCExporterUIWindow type not found -- can't open the native "
            "settings editor; using the setup as-is."
        )
        return None

    # IFCExport and IFCCommandOverrideApplication should live in the
    # same assembly as IFCExporterUIWindow -- pin the search there so
    # we can't accidentally grab an unrelated same-named type from a
    # different loaded assembly.
    try:
        window_asm_name = window_type.Assembly.GetName().Name
    except Exception:
        window_asm_name = None

    # See _set_static_document_context docstring -- fixes the "Import
    # setup..." button (and Classification Settings, Project Address,
    # Category/Property Mapping) closing the whole window unexpectedly.
    for type_name in ("IFCCommandOverrideApplication", "IFCExport"):
        _set_static_document_context(type_name, doc, diagnostics, preferred_assembly_name=window_asm_name)

    try:
        window = System.Activator.CreateInstance(window_type, config_map, initial_setup_name)
    except Exception as ex:
        diagnostics.append("Could not create IFCExporterUIWindow: {}".format(ex))
        return None

    # Button handlers inside this window run on the WPF Dispatcher, not
    # as a normal synchronous call inside our try/except below -- an
    # unhandled exception there is routed to
    # Application.Current.DispatcherUnhandledException FIRST (Revit's
    # own handler, since Revit already owns the process's WPF
    # Application), and unwinds/closes this dialog's message loop
    # BEFORE our own try/except around ShowDialog() ever sees it. That
    # was the actual bug behind "Import closes the window with no
    # visible error": the failure never reached code we control. We
    # attach our own handler to the SAME event (multicast -- this adds
    # a listener, it doesn't replace Revit's), mark each exception
    # Handled so WPF doesn't tear the window down over it, and log it,
    # so at minimum the window stays open and we can see what broke.
    captured_exceptions = []
    dispatcher_handler = None
    app = None
    if _HAS_WPF:
        try:
            app = System.Windows.Application.Current
        except Exception as ex:
            diagnostics.append("  Could not access System.Windows.Application.Current: {}".format(ex))

        if app is not None:
            def _on_dispatcher_exception(sender, event_args):
                try:
                    captured_exceptions.append(str(event_args.Exception))
                    event_args.Handled = True
                except Exception:
                    pass

            try:
                dispatcher_handler = System.Windows.Threading.DispatcherUnhandledExceptionEventHandler(
                    _on_dispatcher_exception
                )
                app.DispatcherUnhandledException += dispatcher_handler
            except Exception as ex:
                diagnostics.append("  Could not attach a DispatcherUnhandledException handler: {}".format(ex))
                dispatcher_handler = None
        else:
            diagnostics.append(
                "  Application.Current is null -- can't intercept in-dialog exceptions; "
                "they may still close the window silently."
            )
    else:
        diagnostics.append("  WPF assemblies not available -- can't intercept in-dialog exceptions.")

    try:
        dialog_result = window.ShowDialog()
    except Exception as ex:
        diagnostics.append("Showing the native settings editor failed: {}".format(ex))
        return None
    finally:
        if app is not None and dispatcher_handler is not None:
            try:
                app.DispatcherUnhandledException -= dispatcher_handler
            except Exception:
                pass

    if captured_exceptions:
        diagnostics.append(
            "Caught {} in-dialog exception(s) that would otherwise have been invisible:".format(
                len(captured_exceptions)
            )
        )
        for exc_text in captured_exceptions:
            diagnostics.append("  " + exc_text)

    if dialog_result is not True:
        diagnostics.append("User cancelled the native settings editor (or it was closed by an error above).")
        return None

    try:
        method = window_type.GetMethod(
            "GetSelectedConfiguration",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance,
        )
        if method is not None:
            selected = method.Invoke(window, None)
            if selected is not None:
                return selected
        diagnostics.append(
            "GetSelectedConfiguration() unavailable via reflection; falling back to "
            "the setup this editor was opened with."
        )
    except Exception as ex:
        diagnostics.append(
            "Reading back the actively-selected configuration failed ({}); "
            "falling back to the setup this editor was opened with.".format(ex)
        )

    try:
        return config_map[initial_setup_name]
    except Exception as ex:
        diagnostics.append("Could not read back the edited configuration: {}".format(ex))
        return None


def build_ifc_export_options(setup, filter_view, doc):
    """
    Turn an IFCSetupInfo into the Autodesk.Revit.DB.IFCExportOptions
    that Document.Export(...) actually needs, scoped to filter_view so
    only that view's visible/isolated geometry is exported.

    IFCExportConfiguration has exposed two different bridges to this,
    depending on Revit version:
      - Older: ToIFCExportOptions() returns a ready-made options object.
      - Newer (confirmed on Revit 2027 / Release_27.x.x): that method
        is gone, replaced by an in-place
        UpdateOptions(doc, options, filterViewId, isNewParameterMappingEnabled)
        -- called the same way by Revit's own Export IFC command.
    """
    if setup.configuration is not None:
        if hasattr(setup.configuration, "ToIFCExportOptions"):
            options = setup.configuration.ToIFCExportOptions()
        else:
            options = IFCExportOptions()
            # False matches Revit's own legacy parameter-mapping
            # default; flip to True to opt into the newer mapping
            # behavior for freshly-created setups.
            setup.configuration.UpdateOptions(doc, options, filter_view.Id, False)
    else:
        options = IFCExportOptions()
        options.FileVersion = setup.ifc_version

    options.FilterViewId = filter_view.Id
    return options
