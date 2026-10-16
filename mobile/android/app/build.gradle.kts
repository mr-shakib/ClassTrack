import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Push notifications need the Firebase project's google-services.json beside this
// file. Without it the app builds and runs as before, with push off.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

// The upload key that signs what goes to Google Play: android/key.properties names
// it. Both stay off git (android/.gitignore) and are kept safely elsewhere; see
// mobile/README.md. Without them a release build is signed with the debug key and
// says so, which is fine on a phone and refused by Play.
val keyProperties = Properties().apply {
    val file = rootProject.file("key.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
val hasUploadKey = keyProperties.getProperty("storeFile")?.let { file(it).exists() } == true

android {
    namespace = "com.bitstreamhq.classtrack"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        // flutter_local_notifications schedules Class Alarm with java.time.
        isCoreLibraryDesugaringEnabled = true
    }

    defaultConfig {
        // The app's identity on Google Play: it can never change once published.
        applicationId = "com.bitstreamhq.classtrack"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasUploadKey) {
            create("upload") {
                storeFile = file(keyProperties.getProperty("storeFile"))
                storePassword = keyProperties.getProperty("storePassword")
                keyAlias = keyProperties.getProperty("keyAlias")
                keyPassword = keyProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (hasUploadKey) {
                signingConfigs.getByName("upload")
            } else {
                logger.warn("No upload key (android/key.properties): signing the release build with the debug key.")
                signingConfigs.getByName("debug")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
