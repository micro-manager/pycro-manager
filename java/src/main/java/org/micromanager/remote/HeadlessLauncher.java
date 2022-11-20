package org.micromanager.remote;

import mmcorej.CMMCore;
import org.micromanager.acqj.internal.Engine;
import org.micromanager.internal.zmq.ZMQServer;

import javax.swing.*;
import javax.swing.plaf.ColorUIResource;
import java.awt.*;
import java.io.UnsupportedEncodingException;
import java.net.URISyntaxException;
import java.util.HashSet;
import java.util.function.Consumer;
import java.util.function.Function;

public class HeadlessLauncher {

   private static Engine engine_;
   private static ZMQServer zmqServer_;

   public static void main(String[] args) throws Exception {

      darkUI();

      CMMCore core = new CMMCore();

      core.waitForSystem();
      int port = Integer.parseInt(args[0]);
      String configFilePath = args[1];
      int bufferSizeMB = Integer.parseInt(args[2]);
      String coreLogPath = args[3];

      core.loadSystemConfiguration(configFilePath);
      core.setCircularBufferMemoryFootprint(bufferSizeMB);
      core.enableStderrLog(true);
      core.enableDebugLog(true);
      core.setPrimaryLogFile(coreLogPath);


      //Start acq Engine
      engine_ = new Engine(core);

      //Start ZMQ server
      Function<Class, Object> instanceGrabberFunction = new Function<Class, Object>() {
         @Override
         public Object apply(Class baseClass) {
            //return instances of existing objects
            if (baseClass.equals(CMMCore.class)) {
               return core;
            }
            return null;
         }
      };


      try {
         HashSet<ClassLoader> classLoaders = new HashSet<ClassLoader>();
         classLoaders.add(core.getClass().getClassLoader());
         zmqServer_ = new ZMQServer(classLoaders, instanceGrabberFunction, new String[]{},
               s -> System.out.println(s), port);
         System.out.println("STARTED");
      } catch (URISyntaxException e) {
         throw new RuntimeException();
      } catch (UnsupportedEncodingException e) {
         throw new RuntimeException();
      }
   }


      // Key into the user's profile for the current display mode.
      private static final String BACKGROUND_MODE =
              "current window style (as per ApplicationSkin.SkinMode)";
      // List of keys to UIManager.put() method for setting the background color
      // look and feel. Selected from this page:
      // http://alvinalexander.com/java/java-uimanager-color-keys-list
      // Each of these keys will have ".background" appended to it later.
      private final  static String[] BACKGROUND_COLOR_KEYS = new String[] {
              "Button", "CheckBox", "ColorChooser", "EditorPane",
              "FormattedTextField", "InternalFrame", "Label", "List", "MenuBar",
              "OptionPane", "Panel", "PasswordField", "ProgressBar",
              "RadioButton", "ScrollBar", "ScrollPane", "Slider", "Spinner",
              "SplitPane", "Table", "TableHeader", "TextArea",
              "TextField", "TextPane", "ToggleButton", "ToolBar", "Tree",
              "Viewport"
      };

      // Keys that get a slightly lighter background for "night" mode. We do this
      // because unfortunately on OSX, the checkmark for selected menu items is
      // 25% gray, and thus invisible against our normal background color.
      private final  static String[] LIGHTER_BACKGROUND_COLOR_KEYS = new String[] {
              "CheckBoxMenuItem", "ComboBox", "Menu", "MenuItem", "PopupMenu",
              "RadioButtonMenuItem"
      };

      // Improve text legibility against dark backgrounds. These will have
      // ".foreground" appended to them later.
      private final  static String[] ENABLED_TEXT_COLOR_KEYS = new String[] {
              "CheckBox", "ColorChooser", "FormattedTextField",
              "InternalFrame", "Label", "List",
              "OptionPane", "Panel", "ProgressBar",
              "RadioButton", "ScrollPane", "Separator", "Slider", "Spinner",
              "SplitPane", "Table", "TableHeader", "TextArea", "TextField",
              "TextPane", "ToolBar", "Tree", "Viewport"
      };

      // As above, but for disabled text; each of these keys will have
      // ".disabledText" appended to it later.
      private final  static String[] DISABLED_TEXT_COLOR_KEYS = new String[] {
              "Button", "CheckBox", "RadioButton", "ToggleButton"
      };

      // Keys that we have to specify manually; nothing will be appended to them.
      private final static String[] MANUAL_TEXT_COLOR_KEYS = new String[] {
              "Tree.textForeground", "TitledBorder.titleColor", "OptionPane.messageForeground"
      };

      // As above, but for background color.
      private final static String[] MANUAL_BACKGROUND_COLOR_KEYS = new String[] {
              "ComboBox.buttonBackground", "Tree.textBackground",
      };



   public static void darkUI() {
      ColorUIResource backgroundMode = new ColorUIResource(new Color(64, 64, 64));
      ColorUIResource disabledTextColor = new ColorUIResource(120, 120, 120);
      ColorUIResource enabledTextColor = new ColorUIResource(200, 200, 200);
      ColorUIResource lightBackground = new ColorUIResource(new Color(96, 96, 96));

      // Ensure every GUI object type gets the right background color.
      for (String key : BACKGROUND_COLOR_KEYS) {
         UIManager.put(key + ".background", backgroundMode);
      }
      for (String key : LIGHTER_BACKGROUND_COLOR_KEYS) {
         UIManager.put(key + ".background", lightBackground);
      }
      for (String key : MANUAL_TEXT_COLOR_KEYS) {
         UIManager.put(key, enabledTextColor);
      }
      for (String key : MANUAL_BACKGROUND_COLOR_KEYS) {
         UIManager.put(key, backgroundMode);
      }
      for (String key : ENABLED_TEXT_COLOR_KEYS) {
         UIManager.put(key + ".foreground", enabledTextColor);
         UIManager.put(key + ".caretForeground", enabledTextColor);
      }
      // Improve contrast of disabled text against backgrounds.
      for (String key : DISABLED_TEXT_COLOR_KEYS) {
         UIManager.put(key + ".disabledText", disabledTextColor);
      }
//      if (shouldUpdateUI) {
//         SwingUtilities.invokeLater(() -> {
//            // Update existing components.
//            for (Window w : Window.getWindows()) {
//               SwingUtilities.updateComponentTreeUI(w);
//            }
//         });
//      }
   }



}
