package org.micromanager.internal.zmq;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.io.UnsupportedEncodingException;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URISyntaxException;
import java.net.URLClassLoader;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import mmcorej.org.json.JSONException;
import mmcorej.org.json.JSONObject;

import org.zeromq.SocketType;

/**
 * implements request reply server (ie the reply part)
 *
 * ecompasses both the master server and the
 */
public class ZMQServer extends ZMQSocketWrapper {

   private ExecutorService executor_;
//   protected static Set<Class> apiClasses_;
   private static Set<String> packages_;
   private static ZMQUtil util_;

   //map of objects that exist in some client of the server
   protected final ConcurrentHashMap<String, Object> externalObjects_ = new ConcurrentHashMap<String, Object>();

   public static final String VERSION = "5.1.0";

   private static Function<Class, Object> classMapper_;
   private static ZMQServer mainServer_;
   static boolean debug_ = false;
   private static Consumer<String> debugLogger_;

   //for testing
//   public static void main(String[] args) {
//      ZMQServer server = new ZMQServer(DEFAULT_MASTER_PORT_NUMBER, "master", new Function<Class, Object>() {
//         @Override
//         public Object apply(Class t) {
//            return null;
//         }
//      });
//      while (true) {
//         if (portSocketMap_.containsKey(DEFAULT_MASTER_PORT_NUMBER + 1)) {
//            ZMQPullSocket socket = (ZMQPullSocket) portSocketMap_.get(DEFAULT_MASTER_PORT_NUMBER + 1);
//            Object n = socket.next();
//            System.out.println();
//         }
//      }
//   }

   /**
    * This constructor used if making a new server on a different port and all the classloader info already parsed
    */
   public ZMQServer()  {
      super(SocketType.REP);
   }

   public ZMQServer(Collection<ClassLoader> cls, Function<Class, Object> classMapper,
                    String[] excludePaths, Consumer<String> debugLogger) throws URISyntaxException, UnsupportedEncodingException {
      this(cls, classMapper, excludePaths, debugLogger, ZMQSocketWrapper.STARTING_PORT_NUMBER);
   }

   public ZMQServer(Collection<ClassLoader> cls, Function<Class, Object> classMapper,
                    String[] excludePaths, Consumer<String> debugLogger, int port) throws URISyntaxException, UnsupportedEncodingException {
      super(SocketType.REP, port);
      mainServer_ = this;
      debugLogger_ = debugLogger;

      classMapper_ = classMapper;
      util_ = new ZMQUtil(cls, excludePaths);

      //get packages for current classloader (redundant?)
      packages_ = ZMQUtil.getPackages();
      for (ClassLoader cl : cls) {
         // Dont understand the launching conditions that make each neccessary, but both needed at times
         if (cl instanceof URLClassLoader) {
            packages_.addAll(ZMQUtil.getPackagesFromJars((URLClassLoader) cl));
         } else  {
            packages_.addAll(Stream.of(Package.getPackages()).map(p -> p.getName()).collect(Collectors.toList()));
         }
      }
   }

   public static ZMQServer getMasterServer() {
      return mainServer_;
   }

   @Override
   public void initialize(int port) {
      // Can we be initialized multiple times?  If so, we should cleanup
      // the multiple instances of executors and sockets cleanly
      executor_ = Executors.newSingleThreadExecutor(
              (Runnable r) -> new Thread(r, "ZMQ Server "));
      executor_.submit(() -> {
         socket_ = context_.createSocket(type_);
         port_ = port;
         socket_.bind("tcp://127.0.0.1:" + port);

         //Master request-reply loop
         while (true) {
            JSONObject message = receiveMessage();
            if (debug_) {
               System.out.println("Recieved message: \t" + message);
               debugLogger_.accept("Recieved message: \t" + message);
            }
            JSONObject reply = null;
            try {
               reply = parseAndExecuteCommand(message);
            } catch (Exception e) {
               try {
                  reply = new JSONObject();
                  reply.put("type", "exception");

                  StringWriter sw = new StringWriter();
                  e.printStackTrace(new PrintWriter(sw));
                  String exceptionAsString = sw.toString();
                  reply.put("value", exceptionAsString);

                  e.printStackTrace();

               } catch (JSONException ex) {
                  throw new RuntimeException(ex);
                  // This wont happen          
               }
            }

            if (debug_) {
               System.out.println("Sending message: \t" + reply.toString());
               debugLogger_.accept("Sending message: \t" + reply.toString());
            }
            sendMessage(reply);
            if (debug_) {
               System.out.println("Message sent");
               debugLogger_.accept("Message sent");
            }
            // Check if any more objects in clients know about this server. If its not the main one,
            // shut it down
            if (this != mainServer_ && externalObjects_.keySet().size() == 0) {
               close();
               break;
            }
         }
      });
   }

   public void close() {
      super.close();
      if (executor_ != null) {
         executor_.shutdownNow();
         socket_.close();
      }
   }

   protected JSONObject getField(Object obj, JSONObject json) throws JSONException, NoSuchFieldException, IllegalArgumentException, IllegalAccessException {
      String fieldName = json.getString("name");
      Object field = obj.getClass().getField(fieldName).get(obj);
      JSONObject serialized = new JSONObject();
      util_.serialize(externalObjects_, field, serialized, port_);
      return serialized;
   }
   
   protected void setField(Object obj, JSONObject json) throws JSONException, NoSuchFieldException, IllegalArgumentException, IllegalAccessException {
      String fieldName = json.getString("name");
      Object val = json.get("value");
      if (val instanceof JSONObject) {
         val = externalObjects_.get(((JSONObject) val).getString("hash-code"));
      }
      obj.getClass().getField(fieldName).set(obj, val);
   }

   /**
    * Traverse the class/interface inheritance hierarchy
    * @param potentialPackages
    */
   private void traverseInheritedPackages(Set<String> potentialPackages, Class classOrInterface) {
      try {
         if (classOrInterface == null) {
            return;
         }
         potentialPackages.add(classOrInterface.getPackage().getName());
         // superclasses
         if (classOrInterface.getSuperclass() != null) {
            traverseInheritedPackages(potentialPackages, classOrInterface.getSuperclass());
         }
         // interfaces
         for (Class c : classOrInterface.getInterfaces()) {
            traverseInheritedPackages(potentialPackages, c);
         }
      } catch (Exception e) {
         e.printStackTrace();
      }
   }

   /**
    * Get reference to object that may be stored on any of the ZMQServers on different ports
    * @param hashCode
    * @return
    */
   private Object getObjectKnownToServer (String hashCode) {
      for (ZMQSocketWrapper z : portSocketMap_.values()) {
         if (z instanceof ZMQServer) {
            if (((ZMQServer) z).externalObjects_.containsKey(hashCode)) {
               return ((ZMQServer) z).externalObjects_.get(hashCode);
            }
         }
      }
      throw new RuntimeException("Object with Hash code " + hashCode + " unknown to all ZMQ servers");
   }

   /**
    * Generate every possible combination of parameters given multiple interfaces for classes so that
    * the correct method can be located. Also fill in argVals with the correct objects or primitives
    *
    * @param message
    * @param argVals
    * @return
    * @throws JSONException
    * @throws UnsupportedEncodingException
    */
   private LinkedList<LinkedList<Class>> getArgumentSignatures(JSONObject message, Object[] argVals) throws JSONException,
           UnsupportedEncodingException {

      //get argument values
      for (int i = 0; i < argVals.length; i++) {
//         Class c = message.getJSONArray("arguments").get(i).getClass();
         if (message.getJSONArray("arguments").get(i) instanceof JSONObject
                 && message.getJSONArray("arguments").getJSONObject(i).has("hash-code")) {
            //Passed in a javashadow object as an argument
            argVals[i] = getObjectKnownToServer(message.getJSONArray("arguments").getJSONObject(i).getString("hash-code"));
         } else if (ZMQUtil.PRIMITIVE_NAME_CLASS_MAP.containsKey(message.getJSONArray("argument-deserialization-types").get(i) )) {
            Object primitive = message.getJSONArray("arguments").get(i); //Double, Integer, Long, Boolean
            Class c = ZMQUtil.PRIMITIVE_NAME_CLASS_MAP.get(message.getJSONArray("argument-deserialization-types").get(i));
            argVals[i] = ZMQUtil.convertToPrimitiveClass(primitive, c);
         } else if (ZMQUtil.PRIMITIVE_ARRAY_NAME_CLASS_MAP.containsKey(message.getJSONArray("argument-deserialization-types").get(i))) {
            byte[] byteArray = (byte[]) message.getJSONArray("arguments").get(i);
            Class c = ZMQUtil.PRIMITIVE_ARRAY_NAME_CLASS_MAP.get(message.getJSONArray("argument-deserialization-types").get(i));
            argVals[i] = ZMQUtil.convertToPrimitiveArray(byteArray, c);
         } else if (message.getJSONArray("argument-deserialization-types").get(i).equals("java.lang.String")) {
            //Strings are a special case because they're like a primitive but not quite
            if (message.getJSONArray("arguments").get(i) == JSONObject.NULL) {
               argVals[i] = null;
            } else {
               argVals[i] = message.getJSONArray("arguments").getString(i);
            }
         } else if (message.getJSONArray("argument-deserialization-types").get(i).equals("java.lang.Object")) {
            argVals[i] = message.getJSONArray("arguments").get(i);
         }
      }


      //get classes
      Object[] argClasses = new Object[message.getJSONArray("arguments").length()];
      for (int i = 0; i < argVals.length; i++) {
//         Class c = message.getJSONArray("arguments").get(i).getClass();
         if (message.getJSONArray("arguments").get(i) instanceof JSONObject
                 && message.getJSONArray("arguments").getJSONObject(i).has("hash-code")) {
            //abstract to superclasses/interfaces in the API
            Set<String> potentialPackages = new TreeSet<String>();
            traverseInheritedPackages(potentialPackages, argVals[i].getClass());

            //build up a list of valid packages
            Set<Class> apiClasses = new HashSet<Class>();
            for (String packageName : potentialPackages) {
               apiClasses.addAll(util_.getPackageClasses(packageName));
            }

            ParamSet<Class> potentialClasses = new ParamSet<Class>();
            for (Class apiClass : apiClasses) {
               if (apiClass.isAssignableFrom(argVals[i].getClass())) {
                  potentialClasses.add(apiClass);
               }
            }
            //add the class itself. This is needed for java internal classes
            potentialClasses.add(argVals[i].getClass());
            argClasses[i] = potentialClasses;
         } else if (ZMQUtil.PRIMITIVE_NAME_CLASS_MAP.containsKey(message.getJSONArray("argument-types").get(i))) {
            argClasses[i] = ZMQUtil.PRIMITIVE_NAME_CLASS_MAP.get(message.getJSONArray("argument-types").get(i));
         } else if (ZMQUtil.PRIMITIVE_ARRAY_NAME_CLASS_MAP.containsKey(message.getJSONArray("argument-types").get(i))) {
            argClasses[i] = ZMQUtil.PRIMITIVE_ARRAY_NAME_CLASS_MAP.get( message.getJSONArray("argument-types").get(i));
         } else if (message.getJSONArray("argument-types").get(i).equals("java.lang.String")) {
            //Strings are a special case because they're like a primitive but not quite
            argClasses[i] = java.lang.String.class;
         } else if (message.getJSONArray("argument-types").get(i).equals("java.lang.Object")) {
            argClasses[i] = java.lang.Object.class;
         }
      }

      //Generate every possible combination of parameters given multiple interfaces for classes
      //so that the correct method can be located
      LinkedList<LinkedList<Class>> paramCombos = new LinkedList<LinkedList<Class>>();
      for (Object argument : argClasses) {
         if (argument instanceof ParamSet) {
            if (paramCombos.isEmpty()) {
               //Add an entry for each possible type of the argument
               for (Class c : (ParamSet<Class>) argument) {
                  paramCombos.add(new LinkedList<Class>());
                  paramCombos.getLast().add(c);
               }
            } else {
               //multiply each existing combo by each possible value of the arg
               LinkedList<LinkedList<Class>> newComboList = new LinkedList<LinkedList<Class>>();
               for (Class c : (ParamSet<Class>) argument) {
                  for (LinkedList<Class> argList : paramCombos) {
                     LinkedList<Class> newArgList = new LinkedList<Class>(argList);
                     newArgList.add(c);
                     newComboList.add(newArgList);
                  }
               }
               paramCombos = newComboList;
            }
         } else {
            //only one type, simply add it to every combo
            if (paramCombos.isEmpty()) {
               //Add an entry for each possible type of the argument
               paramCombos.add(new LinkedList<Class>());
            }
            for (LinkedList<Class> argList : paramCombos) {
               argList.add((Class) argument);
            }
         }
      }
      return paramCombos;
   }

   private Object runConstructor(JSONObject message, Class baseClass) throws
           JSONException, InstantiationException, IllegalAccessException,
           IllegalArgumentException, InvocationTargetException, UnsupportedEncodingException {

      Object[] argVals = new Object[message.getJSONArray("arguments").length()];

      LinkedList<LinkedList<Class>> paramCombos = getArgumentSignatures(message, argVals);

      Constructor mathcingConstructor = null;
      if (paramCombos.isEmpty()) { //Constructor with no arguments
         try {
            mathcingConstructor = baseClass.getConstructor(new Class[]{});
         } catch (Exception ex) {
            throw new RuntimeException(ex);
         }
      } else { //Figure out which constructor matches given arguments
         for (LinkedList<Class> argList : paramCombos) {
            Class[] classArray = argList.stream().toArray(Class[]::new);
            try {
               mathcingConstructor = baseClass.getConstructor(classArray);
               break;
            } catch (NoSuchMethodException e) {
               //ignore
            }
         }
      }
      if (mathcingConstructor == null) {
         throw new RuntimeException("No Matching method found with argumetn types");
      }

      return mathcingConstructor.newInstance(argVals);
   }

   private JSONObject runMethod(Object obj, JSONObject message, boolean staticMethod) throws NoSuchMethodException, IllegalAccessException,
           JSONException, UnsupportedEncodingException {
      /**
       * For static methods the class is the object
       */
      Class clazz;
      if (staticMethod) {
         clazz = (Class) obj;
      } else {
         clazz = obj.getClass();
      }

      String methodName = message.getString("name");
      Object[] argVals = new Object[message.getJSONArray("arguments").length()];
      LinkedList<LinkedList<Class>> paramCombos = getArgumentSignatures(message, argVals);

      Method matchingMethod = null;
      if (paramCombos.isEmpty()) {
         //0 argument funtion
         matchingMethod = clazz.getMethod(methodName);
      } else {
         for (LinkedList<Class> argList : paramCombos) {
            Class[] parameterTypes = argList.stream().toArray(Class[]::new);

            Method[] nameMatches = Stream.of(clazz.getMethods()).filter(
                    method -> method.getName().equals(methodName)).toArray(Method[]::new);

            for (Method m : nameMatches) {
               // if they dont have same number of parameters, its not a match
               if (m.getParameters().length != parameterTypes.length) {
                  continue;
               }
               // Check for equality or superclass compatibility of each parameter
               // this is needed e.g. for the case of a method declared with a parameter List
               // but an argument supplied ArrayList
               // Right now it just takes the first match it finds. It might be better in the future to
               // explicitly find the closest match (for example if it has multiple methods with
               // LinkedList and List as arguments). See:
               // https://stackoverflow.com/questions/2580665/java-getmethod-with-superclass-parameters-in-method
               boolean matches = true;
               for (int i = 0; i < parameterTypes.length; i++) {
                  if (!m.getParameterTypes()[i].isAssignableFrom(parameterTypes[i])) {
                     matches = false;
                     break;
                  }
               }
               if (matches) {
                  matchingMethod = m;
               }
            }

         }
      }
      if (matchingMethod == null) {
         throw new RuntimeException("No Matching method found with argument types");
      }

      Object result;
      try {
         matchingMethod.setAccessible(true); //this is needed to call public methods on private classes
         result = matchingMethod.invoke(obj, argVals);
      } catch (InvocationTargetException ex) {
         ex.printStackTrace();
         result = ex.getCause();
      }

      JSONObject serialized = new JSONObject();
      util_.serialize(externalObjects_, result, serialized, port_);
      return serialized;
   }

   protected JSONObject parseAndExecuteCommand(JSONObject request) throws Exception {
      JSONObject reply;
      switch (request.getString("command")) {
         case "connect": {
            // Connect to the server
            debug_ = request.getBoolean("debug");
            //Called by master process
            reply = new JSONObject();
            reply.put("type", "none");
            reply.put("version", VERSION);
            return reply;
         }
         case "get-constructors": {
            String classpath = request.getString("classpath");
            reply = new JSONObject();
            reply.put("type", "none");
            reply.put("api", ZMQUtil.parseConstructors(classpath, classMapper_));
            return reply;
         }
//         case "get-class":
//            // Get Java class for calling static methods
//            Class baseStaticClass = util_.loadClass(request.getString("classpath"));
//            if (baseStaticClass == null) {
//               throw new RuntimeException("Couldnt find class with name" + request.getString("classpath"));
//            }
//
//            ZMQServer newServer = null;
//            if (request.has("new-port") && request.getBoolean("new-port")) {
//               //start the server for this class and store it
//               newServer = new ZMQServer();
//            }
//            reply = new JSONObject();
//            util_.serialize(baseStaticClass, reply, newServer == null ? port_ :newServer.port_);
//            return reply;
         case "constructor":
            case "get-class": {
               //construct a new object (or grab an exisitng instance)
               // or get a static java class
               Class baseClass = util_.loadClass(request.getString("classpath"));
               if (baseClass == null) {
                  throw new RuntimeException("Couldnt find class with name" + request.getString("classpath"));
               }

               Object instance;
               if (request.getString("command").equals("constructor")) {
                  instance = classMapper_.apply(baseClass);
                  //if this is not one of the classes that is supposed to grab an existing
                  //object, construct a new one
                  if (instance == null) {
                     instance = runConstructor(request, baseClass);
                  }
               } else { //just interested in the class itself
                  instance = baseClass;
               }

               ConcurrentHashMap<String, Object> extObjectTracker = externalObjects_;
               ZMQServer newServer = null;
               if (request.has("new-port") && request.getBoolean("new-port")) {
                  //start the server for this class and store it
                  newServer = new ZMQServer();
                  extObjectTracker = newServer.externalObjects_;
               }
               reply = new JSONObject();
               util_.serialize(extObjectTracker, instance, reply, newServer == null ? port_ : newServer.port_);
               return reply;
         }
         case "run-method": {
            String hashCode = request.getString("hash-code");
            Object target = externalObjects_.get(hashCode);
            return runMethod(target, request, request.getBoolean("static"));
         }
         case "get-field": {
            String hashCode = request.getString("hash-code");
            Object target = externalObjects_.get(hashCode);
            return getField(target, request);
         }
         case "set-field": {
            String hashCode = request.getString("hash-code");
            Object target = externalObjects_.get(hashCode);
            setField(target, request);
            reply = new JSONObject();
            reply.put("type", "none");
            return reply;
         }
         case "destructor": {
            String hashCode = request.getString("hash-code");
            //TODO this is defined in superclass, maybe it would be good to merge these?
//            System.out.println("remove object: " + hashCode);
            Object removed = externalObjects_.remove(hashCode);
            if (debug_) {
               System.out.println("Object ready for garbage collection: " + removed);
            }
            reply = new JSONObject();

            reply.put("type", "none");
            return reply;
         }
         default:
            break;
      }
      throw new RuntimeException("Unknown Command");
   }

}

class ParamSet<E> extends HashSet<E> {

}
