import 'package:flutter/material.dart';
import '../services/storage_service.dart';

class LocaleProvider extends ChangeNotifier {
  final StorageService _storage;
  Locale _locale;

  LocaleProvider(this._storage)
      : _locale = Locale(_storage.getLocale());

  Locale get locale => _locale;

  static const supportedLocales = [
    Locale('ar'),
    Locale('en'),
    Locale('id'),
  ];

  Future<void> setLocale(Locale locale) async {
    if (!supportedLocales.contains(locale)) return;
    _locale = locale;
    await _storage.saveLocale(locale.languageCode);
    notifyListeners();
  }

  String get languageName {
    switch (_locale.languageCode) {
      case 'ar':
        return 'العربية';
      case 'en':
        return 'English';
      case 'id':
        return 'Bahasa Indonesia';
      default:
        return _locale.languageCode;
    }
  }
}
