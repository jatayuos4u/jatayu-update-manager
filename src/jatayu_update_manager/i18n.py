STRINGS = {
'en': {
 'search':'Search packages…', 'failed_generic':'Could not check updates', 'working':'Working…', 'wait':'Please wait for the operation to finish.', 'none_detail':'No APT upgrades were found during the last successful check.', 'not_checked':'Updates not checked yet', 'check_prompt':'Select Check for updates to refresh the package lists.',
 'system_status':'System update status', 'updates_count':'Available updates', 'last_check':'Last checked', 'manager':'Package manager', 'title':'Jatayu Update Manager', 'subtitle':'Keep your JatayuOS system up to date',
 'updates':'Available updates', 'check':'Check for updates', 'install':'Install updates',
 'history':'APT history', 'ready':'Ready. Check for updates to begin.',
 'checking':'Refreshing package lists…', 'installing':'Installing updates…',
 'count':'{count} package update(s) available', 'none':'Your system is up to date.',
 'name':'Package', 'current':'Installed version', 'new':'Available version',
 'admin':'Administrator authentication may be required.', 'success':'Operation completed.',
 'failed':'Operation failed (exit code {code}).', 'busy':'An operation is already running.',
 'language':'Language', 'refresh':'Reload list', 'log':'Operation output',
 'confirm':'Install all available APT upgrades? Review the package list first.',
 'warning':'APT can change system packages. Back up important files first.',
 'restart':'Some updates may require restarting your computer.',
 'refresh_first':'Please check for updates first.', 'cancel':'Cancel', 'yes':'Continue',
 'error':'Error', 'info':'Information', 'history_missing':'APT history is unavailable.'
},
'hi': {
 'search':'पैकेज खोजें…', 'failed_generic':'अपडेट जाँच नहीं हो सकी', 'working':'कार्य जारी है…', 'wait':'कृपया कार्य पूरा होने तक प्रतीक्षा करें।', 'none_detail':'पिछली सफल जाँच में कोई APT अपडेट नहीं मिला।', 'not_checked':'अभी अपडेट की जाँच नहीं हुई', 'check_prompt':'पैकेज सूची अपडेट करने के लिए अपडेट जाँचें चुनें।',
 'system_status':'सिस्टम अपडेट की स्थिति', 'updates_count':'उपलब्ध अपडेट', 'last_check':'पिछली जाँच', 'manager':'पैकेज प्रबंधक', 'title':'जटायु अपडेट प्रबंधक', 'subtitle':'अपने JatayuOS सिस्टम को अपडेट रखें',
 'updates':'उपलब्ध अपडेट', 'check':'अपडेट जाँचें', 'install':'अपडेट इंस्टॉल करें',
 'history':'APT इतिहास', 'ready':'तैयार। शुरू करने के लिए अपडेट जाँचें।',
 'checking':'पैकेज सूची अपडेट हो रही है…', 'installing':'अपडेट इंस्टॉल हो रहे हैं…',
 'count':'{count} पैकेज अपडेट उपलब्ध हैं', 'none':'आपका सिस्टम अपडेट है।',
 'name':'पैकेज', 'current':'इंस्टॉल संस्करण', 'new':'उपलब्ध संस्करण',
 'admin':'प्रशासक की अनुमति आवश्यक हो सकती है।', 'success':'कार्य पूरा हुआ।',
 'failed':'कार्य विफल हुआ (कोड {code})।', 'busy':'एक कार्य पहले से चल रहा है।',
 'language':'भाषा', 'refresh':'सूची फिर लोड करें', 'log':'कार्य का विवरण',
 'confirm':'सभी उपलब्ध APT अपडेट इंस्टॉल करें? पहले सूची जाँच लें।',
 'warning':'APT सिस्टम पैकेज बदल सकता है। पहले ज़रूरी फ़ाइलों का बैकअप लें।',
 'restart':'कुछ अपडेट के बाद कंप्यूटर रीस्टार्ट करना पड़ सकता है।',
 'refresh_first':'पहले अपडेट जाँचें।', 'cancel':'रद्द करें', 'yes':'जारी रखें',
 'error':'त्रुटि', 'info':'जानकारी', 'history_missing':'APT इतिहास उपलब्ध नहीं है।'
}}

def tr(lang, key, **kwargs):
    return STRINGS.get(lang, STRINGS['en']).get(key, key).format(**kwargs)
